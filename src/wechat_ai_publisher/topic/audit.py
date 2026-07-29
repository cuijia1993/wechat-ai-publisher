from __future__ import annotations

import re

from wechat_ai_publisher.domain.models import (
    ClaimRequirement,
    EvidenceContract,
    EvidenceItem,
    EvidenceKind,
    SourceSignal,
    TopicBrief,
)

TYPE_EVIDENCE: dict[str, set[EvidenceKind]] = {
    "workplace_guide": {"official_source", "manual_verification"},
    "life_idea": {"official_source", "manual_verification"},
    "team_workflow": {"official_source", "manual_verification"},
    "case_study": {"runtime_log", "manual_verification"},
    "release_analysis": {"official_source"},
    "migration_checklist": {"official_source"},
    "tutorial": {"code_sample", "manual_verification"},
    "experiment": {"runtime_log", "benchmark"},
    "incident_review": {"runtime_log", "manual_verification"},
    "comparison": {"benchmark", "runtime_log"},
    "opinion": {"official_source"},
}
RUNTIME_WORDS = re.compile(r"实测|跑通|验证了|生产稳定|性能提升|降低了|\d+(?:\.\d+)?%")
SPECIALIST_TITLE = re.compile(
    r"`|(?:^|[\s：])v?\d+\.\d+|/\w+|"
    r"\b[A-Za-z][A-Za-z0-9_]*(?:Repository|Options|Builder)\b|"
    r"\b[a-z][A-Za-z0-9_]*\.[a-zA-Z][A-Za-z0-9_.]*\b"
)


def contains_search_keyword(title: str, keyword: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r"[\s·\-—_:：]+", "", value).casefold()

    normalized_keyword = normalize(keyword)
    return bool(normalized_keyword) and normalized_keyword in normalize(title)


def _official_item(signal: SourceSignal) -> EvidenceItem:
    return EvidenceItem(
        id=f"official:{signal.id}",
        kind="official_source",
        description=f"{signal.source_name}：{signal.title}",
        source_url=signal.url,
        verified=True,
    )


def _downgrade(brief: TopicBrief, signal: SourceSignal, reason: str) -> TopicBrief:
    item = _official_item(signal)
    return brief.model_copy(
        update={
            "decision": "downgrade",
            "content_type": "workplace_guide",
            "title": "AI 替你做决定前，普通人先检查哪些风险",
            "primary_search_keyword": "AI 替你做决定",
            "category": "AI 与生活",
            "core_conclusion": "先确认 AI 建议影响的是钱、隐私、健康还是责任，再核验关键信息，不把完整回答误当成可靠决定。",
            "differentiation": "不复述产品新闻，把技术变化转化为普通人做决定前的风险检查。",
            "reusable_asset": "AI 决策风险检查清单",
            "audience_scope": "broad_public",
            "audience_fit_score": max(brief.audience_fit_score, 75),
            "title_angle": "problem_first",
            "general_reader_value": "不了解具体工具的普通读者也能判断哪些 AI 建议不能直接照做。",
            "prerequisite_knowledge": [],
            "evidence_contract": EvidenceContract(
                items=[item],
                claims=[
                    ClaimRequirement(
                        id="official-change",
                        claim=f"官方资料包含与 {signal.title} 相关的发布或变更信息。",
                        required_kinds=["official_source"],
                        evidence_refs=[item.id],
                        supported=True,
                    )
                ],
                ready_to_write=True,
            ),
            "downgrade_reason": reason,
            "reasoning": f"{brief.reasoning}；已按现有证据降级为大众风险解读。",
        }
    )


def audit_topic_brief(
    brief: TopicBrief,
    signal: SourceSignal,
) -> tuple[TopicBrief, list[str]]:
    if brief.signal_id != signal.id:
        raise ValueError("选题简报引用了候选列表之外的 signal_id")
    if brief.decision == "reject":
        return brief, ["选题 Agent 判定当前信号没有足够内容价值"]

    audience_issues: list[str] = []
    if brief.audience_scope == "specialist":
        audience_issues.append("选题只面向少量深度工具用户")
    if brief.audience_fit_score < 75:
        audience_issues.append("大众读者适配分低于 75")
    if brief.title_angle != "problem_first":
        audience_issues.append("标题以工具或版本为中心，没有先呈现普遍问题")
    if not contains_search_keyword(brief.title, brief.primary_search_keyword):
        audience_issues.append(
            f"标题未包含主搜索词：{brief.primary_search_keyword}"
        )
    if SPECIALIST_TITLE.search(brief.title):
        audience_issues.append("标题包含版本号、配置项或代码标识符")
    if len(brief.prerequisite_knowledge) > 2:
        audience_issues.append("阅读前置知识超过 2 项")
    if len(brief.general_reader_value.strip()) < 12:
        audience_issues.append("没有说明非该工具用户可以获得什么")
    if audience_issues:
        contract = brief.evidence_contract.model_copy(
            update={
                "ready_to_write": False,
                "missing": list(
                    dict.fromkeys(
                        [*brief.evidence_contract.missing, *audience_issues]
                    )
                ),
            }
        )
        return brief.model_copy(
            update={
                "decision": "reject",
                "evidence_contract": contract,
                "downgrade_reason": "；".join(audience_issues),
            }
        ), audience_issues

    official = _official_item(signal)
    provider_items = {item.id: item for item in brief.evidence_contract.items}
    normalized_claims: list[ClaimRequirement] = []
    issues: list[str] = []
    for claim in brief.evidence_contract.claims:
        refs: list[str] = []
        available_kinds: set[EvidenceKind] = set()
        for ref in claim.evidence_refs:
            item = provider_items.get(ref)
            if (
                item
                and item.kind == "official_source"
                and item.source_url == signal.url
            ):
                refs.append(official.id)
                available_kinds.add("official_source")
        supported = bool(set(claim.required_kinds) & available_kinds)
        normalized_claims.append(
            claim.model_copy(
                update={
                    "evidence_refs": list(dict.fromkeys(refs)),
                    "supported": supported,
                }
            )
        )
        if not supported:
            issues.append(f"核心结论缺少对应证据：{claim.claim}")

    required_for_type = TYPE_EVIDENCE[brief.content_type]
    available = {"official_source"}
    if not required_for_type & available:
        issues.append(f"{brief.content_type} 题型缺少所需运行或验证证据")
    if RUNTIME_WORDS.search(f"{brief.title}\n{brief.core_conclusion}"):
        issues.append("标题或核心结论包含实测/效果表述，但当前只有官方来源")
    if not normalized_claims:
        issues.append("选题没有声明可核验的核心结论")

    if issues:
        return _downgrade(brief, signal, "；".join(issues)), issues

    contract = EvidenceContract(
        items=[official],
        claims=normalized_claims,
        missing=[],
        ready_to_write=True,
    )
    return brief.model_copy(update={"evidence_contract": contract}), []

