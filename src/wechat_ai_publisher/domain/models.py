from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    title: str
    url: str
    accessed_at: str


EvidenceKind = Literal[
    "official_source",
    "runtime_log",
    "benchmark",
    "code_sample",
    "screenshot",
    "manual_verification",
]
ContentType = Literal[
    "workplace_guide",
    "life_idea",
    "team_workflow",
    "case_study",
    "release_analysis",
    "migration_checklist",
    "tutorial",
    "experiment",
    "incident_review",
    "comparison",
    "opinion",
]
AudienceScope = Literal["broad_public", "knowledge_worker", "specialist"]


class EvidenceItem(BaseModel):
    id: str
    kind: EvidenceKind
    description: str
    source_url: str | None = None
    verified: bool = False


class ClaimRequirement(BaseModel):
    id: str
    claim: str
    required_kinds: list[EvidenceKind]
    evidence_refs: list[str] = Field(default_factory=list)
    supported: bool = False


class EvidenceContract(BaseModel):
    items: list[EvidenceItem] = Field(default_factory=list)
    claims: list[ClaimRequirement] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    ready_to_write: bool = False


class TopicBrief(BaseModel):
    signal_id: str
    decision: Literal["write", "downgrade", "reject"]
    content_type: ContentType
    title: str
    primary_search_keyword: str = Field(min_length=2, max_length=24)
    category: str
    target_reader: str
    reader_problem: str
    core_conclusion: str
    differentiation: str
    reusable_asset: str
    audience_scope: AudienceScope
    audience_fit_score: int = Field(ge=0, le=100)
    title_angle: Literal["problem_first", "tool_first"]
    general_reader_value: str
    prerequisite_knowledge: list[str] = Field(default_factory=list)
    evidence_contract: EvidenceContract
    reasoning: str
    downgrade_reason: str | None = None


class Topic(BaseModel):
    id: str
    title: str
    primary_search_keyword: str = ""
    category: str
    target_reader: str
    reader_problem: str
    core_conclusion: str
    required_evidence: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    verification_records: list[str] = Field(default_factory=list)
    product_hook: str | None = None
    content_type: ContentType = "opinion"
    audience_scope: AudienceScope = "knowledge_worker"
    audience_fit_score: int = Field(default=70, ge=0, le=100)
    title_angle: Literal["problem_first", "tool_first"] = "problem_first"
    evidence_contract: EvidenceContract | None = None
    score: float = 0
    status: str = "backlog"


class ResearchCard(BaseModel):
    topic_id: str
    target_reader: str
    reader_problem: str
    core_conclusion: str
    facts: list[str] = Field(default_factory=list)
    opinions: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    claim_evidence: dict[str, list[str]] = Field(default_factory=dict)
    ready_to_write: bool = False


class Outline(BaseModel):
    title: str
    digest: str
    sections: list[str]


class Article(BaseModel):
    topic_id: str
    title: str
    digest: str
    markdown: str
    author: str
    publication_status: Literal["candidate", "demo"] = "candidate"


class ReviewResult(BaseModel):
    role: str
    passed: bool
    issues: list[str] = Field(default_factory=list)
    revised_markdown: str | None = None


class EditorialReviewResult(BaseModel):
    role: str = "editorial_reviewer"
    passed: bool
    overall_score: float = Field(ge=0, le=10)
    scores: dict[str, float] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    revised_markdown: str | None = None


class VisualReviewResult(BaseModel):
    role: str = "visual_reviewer"
    passed: bool
    overall_score: float = Field(ge=0, le=10)
    scores: dict[str, float] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)


class GateFinding(BaseModel):
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"


class GateResult(BaseModel):
    passed: bool
    publishable: bool = True
    findings: list[GateFinding] = Field(default_factory=list)


class JobManifest(BaseModel):
    job_id: str
    topic_id: str
    status: str = "created"
    model: str
    prompt_version: str = "v1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    outputs: dict[str, str] = Field(default_factory=dict)
    error: str | None = None


class SourceSignal(BaseModel):
    id: str
    source_name: str
    source_type: Literal["rss", "github", "manual"]
    title: str
    url: str
    summary: str
    published_at: datetime
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    score: float = 0
    tags: list[str] = Field(default_factory=list)


class DiscoveryBatch(BaseModel):
    batch_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    signals: list[SourceSignal] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class TopicSelection(BaseModel):
    signal_id: str
    title: str
    category: str
    target_reader: str
    reader_problem: str
    core_conclusion: str
    required_evidence: list[str] = Field(default_factory=list)
    product_hook: str | None = None
    reasoning: str


class ContentPlan(BaseModel):
    title_candidates: list[str]
    recommended_title: str
    digest: str
    thesis: str
    sections: list[str]
    evidence_to_use: list[str] = Field(default_factory=list)
    claim_ids_to_use: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    reader_takeaway: str
    story_hook: str
    concrete_example: str
    failure_or_twist: str
    plain_language_explanations: dict[str, str] = Field(default_factory=dict)


class VisualBlock(BaseModel):
    id: str
    kind: Literal["key_point", "flowchart", "checklist", "concept_image"]
    anchor: str
    title: str
    description: str = ""
    items: list[str] = Field(default_factory=list)
    prompt: str | None = None


class VisualPlan(BaseModel):
    theme_id: str = "professional-minimal"
    cover_subtitle: str
    blocks: list[VisualBlock] = Field(default_factory=list)


class AssetMetadata(BaseModel):
    id: str
    kind: str
    path: str
    purpose: str
    provider: str
    model: str | None = None
    prompt: str | None = None
    source_url: str | None = None
    copyright_note: str = "由智效进化论模板生成"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ArticleAssets(BaseModel):
    theme_id: str
    cover: AssetMetadata | None = None
    images: list[AssetMetadata] = Field(default_factory=list)
    html_blocks: dict[str, str] = Field(default_factory=dict)


class AgentStep(BaseModel):
    action: str
    status: Literal["running", "completed", "failed", "stopped"]
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    duration_ms: int | None = None
    outputs: dict[str, str] = Field(default_factory=dict)
    error: str | None = None


class AgentRun(BaseModel):
    run_id: str
    status: Literal["running", "completed", "failed", "blocked"] = "running"
    next_action: str = "discover"
    model: str
    prompt_version: str = "agent-v2-evidence-contract"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    steps: list[AgentStep] = Field(default_factory=list)
    outputs: dict[str, str] = Field(default_factory=dict)
    revision_count: int = 0
    revision_counts: dict[str, int] = Field(default_factory=dict)
    max_revisions: int = 2
    max_steps: int = 16
    error: str | None = None

