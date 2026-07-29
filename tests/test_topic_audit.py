from datetime import UTC, datetime

import pytest

from wechat_ai_publisher.domain.models import (
    ClaimRequirement,
    EvidenceContract,
    EvidenceItem,
    SourceSignal,
    TopicBrief,
)
from wechat_ai_publisher.topic.audit import audit_topic_brief


def signal() -> SourceSignal:
    return SourceSignal(
        id="spring-release",
        source_name="Spring AI",
        source_type="github",
        title="Spring AI 2.0.0",
        url="https://github.com/spring-projects/spring-ai/releases/tag/v2.0.0",
        summary="Official release notes.",
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
                    claim="官方发布说明包含本次变化",
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


def test_experiment_without_runtime_evidence_is_downgraded():
    audited, issues = audit_topic_brief(
        brief(content_type="experiment", claim_kind="benchmark"),
        signal(),
    )

    assert issues
    assert audited.decision == "downgrade"
    assert audited.content_type == "workplace_guide"
    assert audited.evidence_contract.ready_to_write
    assert "实测" not in audited.title
    assert audited.audience_scope == "broad_public"
    assert audited.primary_search_keyword in audited.title


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

