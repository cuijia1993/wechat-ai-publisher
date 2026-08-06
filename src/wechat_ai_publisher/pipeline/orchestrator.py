from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml

from wechat_ai_publisher.config import AppConfig
from wechat_ai_publisher.domain.models import Article, JobManifest, Outline, ResearchCard, ReviewResult, Topic
from wechat_ai_publisher.providers.llm import LLMProvider
from wechat_ai_publisher.quality.gates import QualityGate


def load_topics(path: Path) -> list[Topic]:
    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    return [Topic.model_validate(item) for item in payload.get("topics", [])]


def select_topic(topics: list[Topic], topic_id: str | None = None) -> Topic:
    if topic_id:
        for topic in topics:
            if topic.id == topic_id:
                return topic
        raise ValueError(f"找不到选题：{topic_id}")
    selected = [topic for topic in topics if topic.status == "selected"]
    candidates = selected or topics
    if not candidates:
        raise ValueError("选题池为空")
    return max(candidates, key=lambda item: item.score)


class ContentPipeline:
    def __init__(self, config: AppConfig, provider: LLMProvider):
        self.config = config
        self.provider = provider
        prompt_path = config.content.prompt_dir / "stages.yaml"
        with prompt_path.open(encoding="utf-8") as handle:
            self.prompts: dict[str, str] = yaml.safe_load(handle) or {}
        self.style_guide = config.content.style_guide.read_text(encoding="utf-8")

    def _save_model(self, directory: Path, name: str, value) -> Path:
        path = directory / f"{name}.json"
        path.write_text(value.model_dump_json(indent=2), encoding="utf-8")
        return path

    def _save_manifest(self, directory: Path, manifest: JobManifest) -> None:
        manifest.updated_at = datetime.now(UTC)
        (directory / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    def _record(self, directory: Path, manifest: JobManifest, stage: str, value) -> None:
        path = self._save_model(directory, stage, value)
        manifest.outputs[stage] = str(path)
        manifest.status = stage
        self._save_manifest(directory, manifest)

    def run(self, topic: Topic) -> JobManifest:
        job_id = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
        job_dir = self.config.content.output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        manifest = JobManifest(
            job_id=job_id,
            topic_id=topic.id,
            model=self.config.model.resolved_model,
        )
        self._save_manifest(job_dir, manifest)

        try:
            research = self.provider.structured(
                system=self.prompts["researcher"],
                user=json.dumps(topic.model_dump(mode="json"), ensure_ascii=False),
                response_model=ResearchCard,
            )
            research.topic_id = topic.id
            if topic.required_evidence and not topic.verification_records:
                research.ready_to_write = False
                research.missing_evidence = topic.required_evidence
            self._record(job_dir, manifest, "research", research)
            if not research.ready_to_write or research.missing_evidence:
                manifest.status = "evidence_required"
                manifest.error = "资料卡缺少必需证据，流水线已停止"
                self._save_manifest(job_dir, manifest)
                return manifest

            shared_context = {
                "topic": topic.model_dump(mode="json"),
                "research": research.model_dump(mode="json"),
                "style_guide": self.style_guide,
            }
            outline = self.provider.structured(
                system=self.prompts["outline_editor"],
                user=json.dumps(shared_context, ensure_ascii=False),
                response_model=Outline,
            )
            self._record(job_dir, manifest, "outline", outline)

            article = self.provider.structured(
                system=self.prompts["technical_writer"],
                user=json.dumps({**shared_context, "outline": outline.model_dump()}, ensure_ascii=False),
                response_model=Article,
            )
            article.topic_id = topic.id
            article.author = self.config.account.author
            self._record(job_dir, manifest, "draft", article)

            technical_review = self.provider.structured(
                system=self.prompts["technical_reviewer"],
                user=json.dumps(article.model_dump(), ensure_ascii=False),
                response_model=ReviewResult,
            )
            self._record(job_dir, manifest, "technical_review", technical_review)
            if not technical_review.passed and not technical_review.revised_markdown:
                manifest.status = "technical_review_failed"
                self._save_manifest(job_dir, manifest)
                return manifest
            if technical_review.revised_markdown:
                article.markdown = technical_review.revised_markdown

            article = self.provider.structured(
                system=self.prompts["content_editor"],
                user=json.dumps(
                    {"article": article.model_dump(), "style_guide": self.style_guide},
                    ensure_ascii=False,
                ),
                response_model=Article,
            )
            article.topic_id = topic.id
            article.author = self.config.account.author
            self._record(job_dir, manifest, "edited", article)

            compliance_review = self.provider.structured(
                system=self.prompts["compliance_reviewer"],
                user=json.dumps(article.model_dump(), ensure_ascii=False),
                response_model=ReviewResult,
            )
            self._record(job_dir, manifest, "compliance_review", compliance_review)
            if not compliance_review.passed:
                if not compliance_review.revised_markdown:
                    manifest.status = "compliance_review_failed"
                    self._save_manifest(job_dir, manifest)
                    return manifest
                article.markdown = compliance_review.revised_markdown
                self._record(job_dir, manifest, "compliance_revised", article)
                manifest.outputs["edited"] = manifest.outputs["compliance_revised"]
                self._save_manifest(job_dir, manifest)

            gate_result = QualityGate(self.config.quality).check(article, topic)
            self._record(job_dir, manifest, "quality_gate", gate_result)
            article_path = job_dir / "article.md"
            article_path.write_text(article.markdown, encoding="utf-8")
            manifest.outputs["article"] = str(article_path)
            manifest.status = "ready_to_render" if gate_result.passed else "quality_gate_failed"
            self._save_manifest(job_dir, manifest)
            return manifest
        except Exception as exc:
            manifest.status = "failed"
            manifest.error = str(exc)
            self._save_manifest(job_dir, manifest)
            raise

