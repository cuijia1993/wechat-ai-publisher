from datetime import UTC, datetime

import pytest

from wechat_ai_publisher.domain.models import (
    ClaimRequirement,
    EvidenceContract,
    EvidenceItem,
    SourceDocument,
    SourceSignal,
    TopicBrief,
)
from wechat_ai_publisher.topic.audit import audit_enriched_contract, audit_topic_brief


def signal() -> SourceSignal:
    return SourceSignal(
        id="spring-release",
        source_name="Spring AI",
        source_type="github",
        title="Spring AI 2.0.0",
        url="https://github.com/spring-projects/spring-ai/releases/tag/v2.0.0",
        summary="AI 工具发布了新的官方版本说明。",
        published_at=datetime.now(UTC),
    )


def brief(*, content_type="release_analysis", claim_kind="official_source") -> TopicBrief:
    source = signal()
    return TopicBrief(
        signal_id=source.id,
        decision="write",
        content_type=content_type,
        title="AI 工具更新后，普通人怎么判断哪些功能真正值得用",
        primary_search_keyword="AI 工具",
        category="AI 提效",
        target_reader="希望改善日常工作的知识工作者",
        reader_problem="新功能很多，却不知道哪些值得投入时间",
        core_conclusion="先核对官方变化，再用低风险任务验证",
        differentiation="提供普通人能使用的新功能判断清单",
        reusable_asset="AI 新功能采用清单",
        audience_scope="knowledge_worker",
        audience_fit_score=80,
        title_angle="problem_first",
        general_reader_value="不了解具体工具的读者也能复用新功能判断方法。",
        prerequisite_knowledge=["使用过任意 AI 助手"],
        evidence_contract=EvidenceContract(
            items=[
                EvidenceItem(
                    id="source-1",
                    kind=claim_kind,
                    description="候选证据",
                    source_url=source.url,
                    verified=True,
                )
            ],
            claims=[
                ClaimRequirement(
                    id="claim-1",
                    claim="Spring AI 官方发布了 2.0.0 版本说明",
                    required_kinds=[claim_kind],
                    evidence_refs=["source-1"],
                )
            ],
            ready_to_write=True,
        ),
        reasoning="主题可以转化为普通人判断 AI 新功能的方法",
    )


def test_official_release_brief_builds_verified_contract():
    audited, issues = audit_topic_brief(brief(), signal())

    assert issues == []
    assert audited.decision == "write"
    assert audited.evidence_contract.ready_to_write
    assert audited.evidence_contract.claims[0].supported
    assert audited.evidence_contract.claims[0].evidence_refs == [
        "official:spring-release"
    ]


def test_experiment_with_fake_benchmark_evidence_is_rejected():
    audited, issues = audit_topic_brief(
        brief(content_type="experiment", claim_kind="benchmark"),
        signal(),
    )

    assert issues
    assert audited.decision == "reject"
    assert not audited.evidence_contract.ready_to_write


def test_unsupported_content_type_with_official_claim_is_safely_downgraded():
    candidate = brief(content_type="experiment")

    audited, issues = audit_topic_brief(candidate, signal())

    assert issues == ["experiment 题型缺少所需运行或验证证据"]
    assert audited.decision == "downgrade"
    assert audited.content_type == "release_analysis"
    assert audited.title == candidate.title
    assert audited.core_conclusion == candidate.core_conclusion
    assert audited.evidence_contract.ready_to_write


def test_generic_evidence_claim_is_rejected():
    generic = brief()
    generic.evidence_contract.claims[0].claim = "官方资料包含相关发布或变更信息"

    audited, issues = audit_topic_brief(generic, signal())

    assert audited.decision == "reject"
    assert not audited.evidence_contract.ready_to_write
    assert "核心结论过于笼统" in issues[0]


def test_primary_keyword_must_be_grounded_in_source():
    unrelated = brief().model_copy(
        update={
            "title": "AI 替你做决定前，先检查哪些风险",
            "primary_search_keyword": "AI 替你做决定",
        }
    )

    audited, issues = audit_topic_brief(unrelated, signal())

    assert audited.decision == "reject"
    assert "主搜索词与官方来源不一致：AI 替你做决定" in issues


def test_chinese_keyword_can_match_english_source_concepts():
    scam_signal = signal().model_copy(
        update={
            "title": "Disrupting a Criminal Scam Operation",
            "summary": "A scam operation used ChatGPT for investment and impersonation schemes.",
            "tags": ["ai", "scam"],
        }
    )
    candidate = brief().model_copy(
        update={
            "signal_id": scam_signal.id,
            "title": "AI 诈骗出现新套路，普通人如何保护钱包",
            "primary_search_keyword": "AI 诈骗",
        }
    )

    audited, issues = audit_topic_brief(candidate, scam_signal)

    assert issues == []
    assert audited.decision == "write"


def test_compound_chinese_keyword_matches_multiple_english_concepts():
    search_signal = signal().model_copy(
        update={
            "title": "AI Mode helps you book concert tickets",
            "summary": "Use Search to book tickets and plan time offline.",
            "tags": ["ai"],
        }
    )
    candidate = brief().model_copy(
        update={
            "signal_id": search_signal.id,
            "title": "用 AI 搜索订票前要核对哪些信息",
            "primary_search_keyword": "AI 搜索订票",
        }
    )

    audited, issues = audit_topic_brief(candidate, search_signal)

    assert issues == []
    assert audited.decision == "write"


def test_enriched_contract_requires_exact_quote_from_source_document():
    source = signal()
    document = SourceDocument(
        signal_id=source.id,
        title=source.title,
        url=source.url,
        content=(
            "Spring AI 2.0 adds an official migration guide for “application teams”. "
            "The guide lists supported upgrade steps and compatibility limitations."
        ),
        extraction_method="signal_override",
        usable=True,
    )
    contract = EvidenceContract(
        items=[
            EvidenceItem(
                id="quote-1",
                kind="official_source",
                description="官方提供迁移指南",
                source_url=source.url,
                quote='Spring AI 2.0 adds an official migration guide for "application teams".',
            )
        ],
        claims=[
            ClaimRequirement(
                id="claim-1",
                claim="Spring AI 2.0 提供了官方迁移指南",
                required_kinds=["official_source"],
                evidence_refs=["quote-1"],
            )
        ],
        ready_to_write=True,
    )

    audited, issues = audit_enriched_contract(contract, source, document)

    assert issues == []
    assert audited.ready_to_write
    assert audited.items[0].verified
    assert audited.claims[0].supported


def test_enriched_contract_rejects_quote_not_found_in_source():
    source = signal()
    document = SourceDocument(
        signal_id=source.id,
        title=source.title,
        url=source.url,
        content="The official page only announces a version release.",
        usable=True,
    )
    contract = EvidenceContract(
        items=[
            EvidenceItem(
                id="quote-1",
                kind="official_source",
                description="不存在的性能结论",
                source_url=source.url,
                quote="The new release improves performance by fifty percent.",
            )
        ],
        claims=[
            ClaimRequirement(
                id="claim-1",
                claim="新版本性能提升 50%",
                required_kinds=["official_source"],
                evidence_refs=["quote-1"],
            )
        ],
        ready_to_write=True,
    )

    audited, issues = audit_enriched_contract(contract, source, document)

    assert issues
    assert not audited.ready_to_write
    assert not audited.items[0].verified
    assert not audited.claims[0].supported


def test_enriched_contract_rejects_topic_not_supported_by_quotes():
    source = signal()
    content = (
        "Spring AI 2.0 adds an official migration guide for application teams. "
        "The guide lists supported upgrade steps and compatibility limitations."
    )
    document = SourceDocument(
        signal_id=source.id,
        title=source.title,
        url=source.url,
        content=content,
        extraction_method="signal_override",
        usable=True,
    )
    contract = EvidenceContract(
        items=[
            EvidenceItem(
                id="quote-1",
                kind="official_source",
                description="官方提供迁移指南",
                source_url=source.url,
                quote=content,
            )
        ],
        claims=[
            ClaimRequirement(
                id="claim-1",
                claim="Spring AI 2.0 提供了官方迁移指南",
                required_kinds=["official_source"],
                evidence_refs=["quote-1"],
            )
        ],
        topic_supported=False,
        ready_to_write=False,
    )

    audited, issues = audit_enriched_contract(contract, source, document)

    assert not audited.ready_to_write
    assert "官方全文不足以支持当前标题" in "\n".join(issues)


def test_brief_cannot_select_signal_outside_candidates():
    invalid = brief().model_copy(update={"signal_id": "other"})

    with pytest.raises(ValueError, match="signal_id"):
        audit_topic_brief(invalid, signal())


def test_specialist_tool_first_topic_is_rejected():
    narrow = brief().model_copy(
        update={
            "title": "Spring AI 2.0.0 ChatMemoryRepository 迁移细节",
            "audience_scope": "specialist",
            "audience_fit_score": 35,
            "title_angle": "tool_first",
            "prerequisite_knowledge": ["Spring AI", "MCP", "ChatMemory"],
        }
    )

    audited, issues = audit_topic_brief(narrow, signal())

    assert issues
    assert audited.decision == "reject"
    assert not audited.evidence_contract.ready_to_write


def test_topic_below_mass_audience_threshold_is_rejected():
    narrow = brief().model_copy(update={"audience_fit_score": 74})

    audited, issues = audit_topic_brief(narrow, signal())

    assert "大众读者适配分低于 75" in issues
    assert audited.decision == "reject"


def test_title_without_primary_search_keyword_is_rejected():
    missing_keyword = brief().model_copy(
        update={"primary_search_keyword": "微信支付 AI 专属卡"}
    )

    audited, issues = audit_topic_brief(missing_keyword, signal())

    assert "标题未包含主搜索词：微信支付 AI 专属卡" in issues
    assert audited.decision == "reject"

