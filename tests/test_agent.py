import json
from datetime import UTC, datetime
from pathlib import Path

from wechat_ai_publisher.agent.runner import ContentOperationsAgent
from wechat_ai_publisher.config import SourcesConfig, load_config
from wechat_ai_publisher.discovery.client import DiscoveryClient
from wechat_ai_publisher.domain.models import (
    EditorialReviewResult,
    GateResult,
    ResearchCard,
    ReviewResult,
    SourceDocument,
    SourceSignal,
    TopicBrief,
    VisualBlock,
    VisualPlan,
    VisualReviewResult,
)
from wechat_ai_publisher.export.draft_writer import DraftWriter
from wechat_ai_publisher.providers.demo import DemoProvider
from wechat_ai_publisher.quality.gates import QualityGate
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


def build_agent(
    tmp_path: Path,
    provider=None,
    image_provider=None,
    *,
    signals=None,
    source_fetcher=None,
    require_topic_approval=False,
) -> ContentOperationsAgent:
    config = load_config(ROOT / "config" / "account.example.yaml")
    config.content.output_dir = tmp_path / "runtime"
    config.agent.max_steps = 24
    config.agent.max_revisions = 2
    config.agent.require_topic_approval = require_topic_approval
    return ContentOperationsAgent(
        config,
        provider or DemoProvider(),
        DiscoveryClient(SourcesConfig()),
        DraftWriter(tmp_path / "drafts", WechatFormatter(ROOT / "templates" / "article.html")),
        signals_override=signals or [signal()],
        source_fetcher=source_fetcher,
        image_provider=image_provider,
    )


def test_agent_runs_to_local_draft_and_resume_is_idempotent(tmp_path, capsys):
    agent = build_agent(tmp_path)

    state = agent.run()
    captured = capsys.readouterr()

    assert state.status == "completed"
    assert captured.out == ""
    assert '"event": "step_started"' in captured.err
    assert '"event": "step_finished"' in captured.err
    assert Path(state.outputs["draft_markdown"]).is_file()
    assert Path(state.outputs["draft_html"]).is_file()
    assert Path(state.outputs["visual_manifest"]).is_file()
    assert Path(state.outputs["cover"]).is_file()
    publication_manifest = json.loads(
        Path(state.outputs["publication_manifest"]).read_text(encoding="utf-8")
    )
    assert publication_manifest["status"] == "ready_to_publish"
    assert publication_manifest["job_id"].startswith("agent-")
    assert all(
        not Path(value).is_absolute()
        for value in publication_manifest["outputs"].values()
    )
    assert Path(state.outputs["topic_brief"]).is_file()
    assert Path(state.outputs["evidence_contract"]).is_file()
    assert [step.action for step in state.steps] == [
        "discover",
        "select",
        "enrich_source",
        "refine_topic",
        "build_evidence",
        "research",
        "plan",
        "write",
        "review",
        "gate",
        "editorial_review",
        "visual_plan",
        "render_assets",
        "visual_review",
        "export",
    ]

    resumed = agent.resume(state.run_id)
    assert len(resumed.steps) == len(state.steps)
    assert resumed.outputs == state.outputs


def test_agent_waits_for_topic_approval_before_research(tmp_path):
    agent = build_agent(tmp_path, require_topic_approval=True)

    pending = agent.run()

    assert pending.status == "awaiting_approval"
    assert pending.topic_approval_status == "pending"
    assert pending.next_action == "stop"
    assert [step.action for step in pending.steps][-1] == "await_topic_approval"
    approval = json.loads(
        Path(pending.outputs["topic_approval"]).read_text(encoding="utf-8")
    )
    assert approval["title"]
    assert approval["source"]["url"] == signal().url
    assert "research" not in pending.outputs

    unchanged = agent.resume(pending.run_id)
    assert len(unchanged.steps) == len(pending.steps)

    agent.approve_topic(
        pending.run_id,
        actor="reviewer@example.com",
        note="标题和证据可以进入写作",
    )
    completed = agent.resume(pending.run_id)

    assert completed.status == "completed"
    assert completed.topic_approval_status == "approved"
    assert completed.topic_approval_actor == "reviewer@example.com"
    assert Path(completed.outputs["draft_html"]).is_file()


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
    assert [step.action for step in state.steps] == ["discover", "select", "select"]
    assert state.rejected_signal_ids == [signal().id]
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
    assert [step.action for step in state.steps][-2:] == ["research", "select"]
    assert state.rejected_signal_ids == [signal().id]
    research = json.loads(Path(state.outputs["research"]).read_text(encoding="utf-8"))
    assert research["missing_evidence"]


class FailFirstSourceFetcher:
    def fetch(self, candidate: SourceSignal) -> SourceDocument:
        if candidate.id == "bad-source":
            return SourceDocument(
                signal_id=candidate.id,
                title=candidate.title,
                url=candidate.url,
                usable=False,
                error="官方页面要求人机验证",
            )
        return SourceDocument(
            signal_id=candidate.id,
            title=candidate.title,
            url=candidate.url,
            content=candidate.summary,
            content_type="text/plain",
            extraction_method="test",
            content_hash="test-hash",
            usable=True,
        )


def test_agent_tries_next_candidate_when_source_cannot_be_fetched(tmp_path):
    bad = signal().model_copy(
        update={
            "id": "bad-source",
            "url": "https://example.com/bad",
            "score": 200,
        }
    )
    good = signal().model_copy(
        update={
            "id": "good-source",
            "title": "Spring AI Agent Good Update",
            "url": "https://good.example.org/good",
            "summary": (
                "Spring AI Agent Good Update provides detailed official information "
                "about Java agent testing and observability."
            ),
            "score": 100,
        }
    )
    state = build_agent(
        tmp_path,
        signals=[bad, good],
        source_fetcher=FailFirstSourceFetcher(),
    ).run()

    assert state.status == "completed"
    assert state.rejected_signal_ids == ["bad-source"]
    assert state.rejected_source_hosts == ["example.com"]
    assert json.loads(
        Path(state.outputs["selected_signal"]).read_text(encoding="utf-8")
    )["id"] == "good-source"


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
                    revised_markdown=article["markdown"].replace(
                        "\n\n## 参考资料",
                        "\n\n本文仅用于验证 Agent 工作流。\n\n## 参考资料",
                    ),
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


class GateThenReviewerRevisionProvider(DemoProvider):
    def __init__(self):
        self.review_count = 0

    def structured(self, *, system: str, user: str, response_model):
        if response_model is ReviewResult:
            self.review_count += 1
            if self.review_count == 1:
                return ReviewResult(role="reviewer", passed=True)
            if self.review_count == 2:
                article = json.loads(user)["article"]
                return ReviewResult(
                    role="reviewer",
                    passed=False,
                    issues=["修正门禁反馈后仍有一处内容问题"],
                    revised_markdown=article["markdown"] + "\n\n补充人工确认边界。",
                )
            return ReviewResult(role="reviewer", passed=True)
        return super().structured(system=system, user=user, response_model=response_model)


def test_revision_limits_are_tracked_per_review_stage(tmp_path, monkeypatch):
    gate_calls = 0

    def staged_gate(self, article, topic, *, historical_titles=None):
        nonlocal gate_calls
        gate_calls += 1
        return GateResult(
            passed=gate_calls > 1,
            findings=[] if gate_calls > 1 else [],
        )

    monkeypatch.setattr(QualityGate, "check", staged_gate)
    agent = build_agent(tmp_path, GateThenReviewerRevisionProvider())
    agent.config.agent.max_steps = 24

    state = agent.run()

    assert state.status == "completed"
    assert state.revision_count == 2
    assert state.revision_counts == {
        "quality_gate": 1,
        "content_review": 1,
    }


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
                    revised_markdown=article["markdown"].replace(
                        "\n\n## 参考资料",
                        "\n\n以上结论仅适用于给定证据范围。\n\n## 参考资料",
                    ),
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


class EditorialPassedWithRevisionProvider(DemoProvider):
    def __init__(self):
        self.editorial_review_count = 0

    def structured(self, *, system: str, user: str, response_model):
        if response_model is EditorialReviewResult:
            self.editorial_review_count += 1
            if self.editorial_review_count == 1:
                article = json.loads(user)["article"]
                return EditorialReviewResult(
                    passed=True,
                    overall_score=9,
                    scores={"factual_accuracy": 9},
                    revised_markdown=article["markdown"].replace(
                        "\n\n## 参考资料",
                        "\n\n主编修正了证据边界。\n\n## 参考资料",
                    ),
                )
        return super().structured(system=system, user=user, response_model=response_model)


def test_editorial_revision_is_applied_even_when_reviewer_marks_passed(tmp_path):
    state = build_agent(tmp_path, EditorialPassedWithRevisionProvider()).run()

    assert state.status == "completed"
    assert state.revision_counts["editorial_review"] == 1
    assert [step.action for step in state.steps].count("editorial_review") == 2
    assert "主编修正了证据边界" in Path(
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
    agent = build_agent(tmp_path, RejectVisualProvider())
    agent.config.model.supports_vision = True
    state = agent.run()

    assert state.status == "blocked"
    assert state.next_action == "stop"
    assert [step.action for step in state.steps][-1] == "visual_review"
    assert "visual_review" in state.outputs
    assert "draft_markdown" not in state.outputs
    assert "publication_manifest" not in state.outputs


class TextOnlyVisualProvider(DemoProvider):
    def structured_with_images(self, **kwargs):
        raise AssertionError("文本模型不应收到图片消息")


def test_text_only_model_uses_metadata_visual_review(tmp_path):
    agent = build_agent(tmp_path, TextOnlyVisualProvider())
    agent.config.model.supports_vision = False

    state = agent.run()

    assert state.status == "completed"
    assert Path(state.outputs["visual_review"]).is_file()


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


def test_agent_falls_back_to_single_html_card_when_static_image_fails(tmp_path):
    state = build_agent(
        tmp_path,
        ConceptVisualProvider(),
        FailingImageProvider(),
    ).run()

    assert state.status == "completed"
    manifest = json.loads(Path(state.outputs["visual_manifest"]).read_text(encoding="utf-8"))
    assert manifest["images"] == []
    block = manifest["html_blocks"]["AI 工作流设计"]
    assert block.count("受控 Agent 工作流") == 1

