import json
from datetime import UTC, datetime
from pathlib import Path

from wechat_ai_publisher.agent.runner import ContentOperationsAgent
from wechat_ai_publisher.config import SourcesConfig, load_config
from wechat_ai_publisher.discovery.client import DiscoveryClient
from wechat_ai_publisher.domain.models import (
    EditorialReviewResult,
    ResearchCard,
    ReviewResult,
    SourceSignal,
    TopicBrief,
    VisualBlock,
    VisualPlan,
    VisualReviewResult,
)
from wechat_ai_publisher.export.draft_writer import DraftWriter
from wechat_ai_publisher.providers.demo import DemoProvider
from wechat_ai_publisher.rendering.formatter import WechatFormatter


ROOT = Path(__file__).resolve().parents[1]


def signal() -> SourceSignal:
    return SourceSignal(
        id="agent-test-signal",
        source_name="Spring AI Test",
        source_type="manual",
        title="Spring AI Agent Test Update",
        url="https://example.com/spring-ai-agent-test",
        summary="Java agent MCP observability and testing update.",
        published_at=datetime.now(UTC),
        score=100,
        tags=["java", "spring", "agent"],
    )


def build_agent(tmp_path: Path, provider=None, image_provider=None) -> ContentOperationsAgent:
    config = load_config(ROOT / "config" / "account.example.yaml")
    config.content.output_dir = tmp_path / "runtime"
    config.agent.max_steps = 16
    config.agent.max_revisions = 2
    return ContentOperationsAgent(
        config,
        provider or DemoProvider(),
        DiscoveryClient(SourcesConfig()),
        DraftWriter(tmp_path / "drafts", WechatFormatter(ROOT / "templates" / "article.html")),
        signals_override=[signal()],
        image_provider=image_provider,
    )


def test_agent_runs_to_local_draft_and_resume_is_idempotent(tmp_path):
    agent = build_agent(tmp_path)

    state = agent.run()

    assert state.status == "completed"
    assert Path(state.outputs["draft_markdown"]).is_file()
    assert Path(state.outputs["draft_html"]).is_file()
    assert Path(state.outputs["visual_manifest"]).is_file()
    assert Path(state.outputs["cover"]).is_file()
    assert Path(state.outputs["topic_brief"]).is_file()
    assert Path(state.outputs["evidence_contract"]).is_file()
    assert [step.action for step in state.steps] == [
        "discover",
        "select",
        "research",
        "plan",
        "visual_plan",
        "write",
        "review",
        "gate",
        "editorial_review",
        "render_assets",
        "visual_review",
        "export",
    ]

    resumed = agent.resume(state.run_id)
    assert len(resumed.steps) == len(state.steps)
    assert resumed.outputs == state.outputs


class FailSelectionOnceProvider(DemoProvider):
    def __init__(self):
        self.failed = False

    def structured(self, *, system: str, user: str, response_model):
        if response_model is TopicBrief and not self.failed:
            self.failed = True
            raise RuntimeError("temporary model failure")
        return super().structured(system=system, user=user, response_model=response_model)


def test_resume_retries_failed_step_without_repeating_discovery(tmp_path):
    provider = FailSelectionOnceProvider()
    agent = build_agent(tmp_path, provider)

    failed = agent.run()
    assert failed.status == "failed"
    assert [step.action for step in failed.steps] == ["discover", "select"]

    completed = agent.resume(failed.run_id)
    assert completed.status == "completed"
    assert [step.action for step in completed.steps].count("discover") == 1
    assert [step.action for step in completed.steps].count("select") == 2


class RejectTopicProvider(DemoProvider):
    def structured(self, *, system: str, user: str, response_model):
        value = super().structured(
            system=system,
            user=user,
            response_model=response_model,
        )
        if response_model is TopicBrief:
            return value.model_copy(update={"decision": "reject"})
        return value


def test_topic_agent_stops_before_research_when_topic_is_rejected(tmp_path):
    state = build_agent(tmp_path, RejectTopicProvider()).run()

    assert state.status == "blocked"
    assert [step.action for step in state.steps] == ["discover", "select"]
    assert "topic_brief" in state.outputs
    assert "research" not in state.outputs


class UnboundResearchProvider(DemoProvider):
    def structured(self, *, system: str, user: str, response_model):
        value = super().structured(
            system=system,
            user=user,
            response_model=response_model,
        )
        if response_model is ResearchCard:
            return value.model_copy(update={"claim_evidence": {}})
        return value


def test_agent_stops_when_research_does_not_bind_claim_evidence(tmp_path):
    state = build_agent(tmp_path, UnboundResearchProvider()).run()

    assert state.status == "blocked"
    assert [step.action for step in state.steps][-1] == "research"
    research = json.loads(Path(state.outputs["research"]).read_text(encoding="utf-8"))
    assert research["missing_evidence"]


class RevisionOnceProvider(DemoProvider):
    def __init__(self):
        self.review_count = 0

    def structured(self, *, system: str, user: str, response_model):
        if response_model is ReviewResult:
            self.review_count += 1
            if self.review_count == 1:
                article = json.loads(user)["article"]
                return ReviewResult(
                    role="combined_reviewer",
                    passed=False,
                    issues=["需要补充演示边界"],
                    revised_markdown=article["markdown"] + "\n\n本文仅用于验证 Agent 工作流。",
                )
        return super().structured(system=system, user=user, response_model=response_model)


def test_agent_applies_review_revision_and_rechecks(tmp_path):
    provider = RevisionOnceProvider()
    state = build_agent(tmp_path, provider).run()

    assert state.status == "completed"
    assert state.revision_count == 1
    actions = [step.action for step in state.steps]
    assert actions.count("review") == 2
    assert "revise" in actions
    assert "仅用于验证 Agent 工作流" in Path(state.outputs["draft_markdown"]).read_text(encoding="utf-8")


class EditorialRevisionOnceProvider(DemoProvider):
    def __init__(self):
        self.editorial_review_count = 0

    def structured(self, *, system: str, user: str, response_model):
        if response_model is EditorialReviewResult:
            self.editorial_review_count += 1
            if self.editorial_review_count == 1:
                article = json.loads(user)["article"]
                return EditorialReviewResult(
                    passed=False,
                    overall_score=7,
                    scores={"evidence_density": 7},
                    issues=["结尾缺少明确的证据边界"],
                    revised_markdown=article["markdown"] + "\n\n以上结论仅适用于给定证据范围。",
                )
        return super().structured(system=system, user=user, response_model=response_model)


def test_editorial_reviewer_revises_before_rendering(tmp_path):
    state = build_agent(tmp_path, EditorialRevisionOnceProvider()).run()

    assert state.status == "completed"
    actions = [step.action for step in state.steps]
    assert actions.count("editorial_review") == 2
    assert actions.index("editorial_review") < actions.index("render_assets")
    assert "以上结论仅适用于给定证据范围" in Path(
        state.outputs["draft_markdown"]
    ).read_text(encoding="utf-8")


class RejectVisualProvider(DemoProvider):
    def structured_with_images(
        self, *, system: str, user: str, image_paths: list[Path], response_model
    ):
        if response_model is VisualReviewResult:
            return VisualReviewResult(
                passed=False,
                overall_score=6,
                scores={"information_value": 5},
                issues=["封面副标题存在过度承诺"],
            )
        return super().structured_with_images(
            system=system,
            user=user,
            image_paths=image_paths,
            response_model=response_model,
        )


def test_visual_reviewer_blocks_export(tmp_path):
    state = build_agent(tmp_path, RejectVisualProvider()).run()

    assert state.status == "blocked"
    assert state.next_action == "stop"
    assert [step.action for step in state.steps][-1] == "visual_review"
    assert "visual_review" in state.outputs
    assert "draft_markdown" not in state.outputs


class ConceptVisualProvider(DemoProvider):
    def structured(self, *, system: str, user: str, response_model):
        if response_model is VisualPlan:
            return VisualPlan(
                cover_subtitle="静态生图失败也能完成草稿",
                blocks=[
                    VisualBlock(
                        id="concept",
                        kind="concept_image",
                        anchor="AI 工作流设计",
                        title="受控 Agent 工作流",
                        description="生成、验证、审查与采用",
                        items=["生成候选", "执行验证", "人工采用"],
                        prompt="深蓝青绿色专业极简抽象流程，无文字",
                    )
                ],
            )
        return super().structured(system=system, user=user, response_model=response_model)


class FailingImageProvider:
    name = "failing-test"
    model = "static-image-test"

    def generate(self, **kwargs):
        raise TimeoutError("image timeout")


def test_agent_falls_back_to_template_when_static_image_fails(tmp_path):
    state = build_agent(
        tmp_path,
        ConceptVisualProvider(),
        FailingImageProvider(),
    ).run()

    assert state.status == "completed"
    manifest = json.loads(Path(state.outputs["visual_manifest"]).read_text(encoding="utf-8"))
    assert manifest["images"][0]["provider"] == "pillow-template-fallback"

