from __future__ import annotations

import re

from wechat_ai_publisher.domain.models import (
    ClaimRequirement,
    EvidenceContract,
    EvidenceItem,
    EvidenceKind,
    SourceDocument,
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
GENERIC_CLAIM = re.compile(
    r"官方资料(?:中)?(?:包含|提到|介绍)|相关的?(?:发布|变更|信息|内容)|"
    r"本文(?:将|会)|值得关注|可供参考"
)
KEYWORD_ALIASES: dict[str, tuple[str, ...]] = {
    "ai": ("ai", "chatgpt", "人工智能"),
    "诈骗": ("诈骗", "scam", "fraud"),
    "隐私": ("隐私", "privacy"),
    "工具": ("工具", "tool"),
    "搜索": ("搜索", "search"),
    "订票": ("订票", "book", "booking", "ticket"),
    "订单": ("订单", "order"),
    "攻略": ("攻略", "guide", "plan", "planning"),
    "地点": ("地点", "place", "location"),
    "旅行": ("旅行", "travel", "trip"),
    "购物": ("购物", "shopping", "shop"),
    "视频": ("视频", "video"),
    "工作": ("工作", "work", "productivity"),
    "手机": ("手机", "phone", "android"),
    "生活": ("生活", "life", "real world", "offline"),
    "助手": ("助手", "assistant", "help", "tool"),
    "数字": ("数字", "digital"),
    "分身": ("分身", "avatar"),
    "家庭": ("家庭", "family", "home"),
    "聚餐": ("聚餐", "dinner", "meal", "gathering", "party"),
    "裁员": ("裁员", "layoff"),
    "工资": ("工资", "salary", "wage"),
}
QUOTE_PUNCTUATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "–": "-",
        "—": "-",
        "\u00a0": " ",
    }
)
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


def text_supports_keyword(source_text: str, keyword: str) -> bool:
    source_text = source_text.casefold()
    if contains_search_keyword(source_text, keyword):
        return True
    tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", keyword.casefold())
    if not tokens:
        return False
    alias_groups: list[tuple[str, ...]] = []
    chinese_keys = [
        key for key in KEYWORD_ALIASES if re.fullmatch(r"[\u4e00-\u9fff]+", key)
    ]
    for token in tokens:
        if token in KEYWORD_ALIASES:
            alias_groups.append(KEYWORD_ALIASES[token])
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            remaining = token
            for stopword in ("做", "用", "帮", "找"):
                remaining = remaining.replace(stopword, "")
            matched: list[str] = []
            for key in sorted(chinese_keys, key=len, reverse=True):
                if key in remaining:
                    matched.append(key)
                    remaining = remaining.replace(key, "")
            if matched and not remaining:
                alias_groups.extend(KEYWORD_ALIASES[key] for key in matched)
                continue
        alias_groups.append((token,))
    return all(
        any(alias.casefold() in source_text for alias in aliases)
        for aliases in alias_groups
    )


def source_supports_keyword(signal: SourceSignal, keyword: str) -> bool:
    return text_supports_keyword(
        f"{signal.title}\n{signal.summary}\n{' '.join(signal.tags)}",
        keyword,
    )


def audit_enriched_contract(
    contract: EvidenceContract,
    signal: SourceSignal,
    document: SourceDocument,
) -> tuple[EvidenceContract, list[str]]:
    normalized_document = (
        re.sub(r"\s+", " ", document.content.translate(QUOTE_PUNCTUATION))
        .strip()
        .casefold()
    )
    verified_items: list[EvidenceItem] = []
    issues: list[str] = []
    for item in contract.items:
        quote = re.sub(r"\s+", " ", item.quote or "").strip()
        normalized_quote = quote.translate(QUOTE_PUNCTUATION).casefold()
        verified = (
            item.kind == "official_source"
            and item.source_url in {signal.url, document.url}
            and len(normalized_quote) >= 20
            and normalized_quote in normalized_document
        )
        verified_items.append(item.model_copy(update={"quote": quote or None, "verified": verified}))
        if not verified:
            issues.append(f"证据项没有绑定可定位的官方原文：{item.description}")

    item_map = {item.id: item for item in verified_items if item.verified}
    normalized_claims: list[ClaimRequirement] = []
    for claim in contract.claims:
        refs = list(dict.fromkeys(ref for ref in claim.evidence_refs if ref in item_map))
        kinds = {item_map[ref].kind for ref in refs}
        supported = (
            bool(refs)
            and bool(set(claim.required_kinds) & kinds)
            and not GENERIC_CLAIM.search(claim.claim)
        )
        normalized_claims.append(
            claim.model_copy(update={"evidence_refs": refs, "supported": supported})
        )
        if not supported:
            issues.append(f"核心结论没有可核验原文：{claim.claim}")

    minimum_claims = 1 if document.extraction_method == "signal_override" else 2
    if len(normalized_claims) < minimum_claims:
        issues.append(
            f"官方全文只形成 {len(normalized_claims)} 条具体结论，"
            f"至少需要 {minimum_claims} 条"
        )
    if not contract.topic_supported:
        issues.append("官方全文不足以支持当前标题、核心结论或可复制资产")
    issues = list(dict.fromkeys([*contract.missing, *issues]))
    audited = EvidenceContract(
        items=verified_items,
        claims=normalized_claims,
        missing=issues,
        topic_supported=contract.topic_supported,
        ready_to_write=bool(normalized_claims) and not issues,
    )
    return audited, issues


def _official_item(signal: SourceSignal) -> EvidenceItem:
    return EvidenceItem(
        id=f"official:{signal.id}",
        kind="official_source",
        description=f"{signal.source_name}：{signal.title}。来源摘要：{signal.summary}",
        source_url=signal.url,
        verified=True,
    )


def _reject(
    brief: TopicBrief,
    official: EvidenceItem,
    claims: list[ClaimRequirement],
    issues: list[str],
) -> TopicBrief:
    contract = EvidenceContract(
        items=[official],
        claims=claims,
        missing=list(dict.fromkeys(issues)),
        ready_to_write=False,
    )
    return brief.model_copy(
        update={
            "decision": "reject",
            "evidence_contract": contract,
            "downgrade_reason": "；".join(issues),
        }
    )


def audit_topic_brief(
    brief: TopicBrief,
    signal: SourceSignal,
    *,
    enforce_source_grounding: bool = True,
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
    if enforce_source_grounding and not source_supports_keyword(
        signal, brief.primary_search_keyword
    ):
        audience_issues.append(
            f"主搜索词与官方来源不一致：{brief.primary_search_keyword}"
        )
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
        generic = bool(GENERIC_CLAIM.search(claim.claim))
        supported = bool(set(claim.required_kinds) & available_kinds) and not generic
        normalized_claims.append(
            claim.model_copy(
                update={
                    "evidence_refs": list(dict.fromkeys(refs)),
                    "supported": supported,
                }
            )
        )
        if generic:
            issues.append(f"核心结论过于笼统，无法核验：{claim.claim}")
        elif not supported:
            issues.append(f"核心结论缺少对应证据：{claim.claim}")

    required_for_type = TYPE_EVIDENCE[brief.content_type]
    available = {"official_source"}
    type_issue = False
    if not required_for_type & available:
        type_issue = True
        issues.append(f"{brief.content_type} 题型缺少所需运行或验证证据")
    if RUNTIME_WORDS.search(f"{brief.title}\n{brief.core_conclusion}"):
        issues.append("标题或核心结论包含实测/效果表述，但当前只有官方来源")
    if not normalized_claims:
        issues.append("选题没有声明可核验的核心结论")

    contract = EvidenceContract(
        items=[official],
        claims=normalized_claims,
        missing=list(dict.fromkeys(issues)),
        ready_to_write=not issues,
    )
    blocking_issues = [
        issue
        for issue in issues
        if issue != f"{brief.content_type} 题型缺少所需运行或验证证据"
    ]
    if blocking_issues:
        return _reject(brief, official, normalized_claims, issues), issues
    if type_issue:
        downgraded = brief.model_copy(
            update={
                "decision": "downgrade",
                "content_type": "release_analysis",
                "evidence_contract": contract.model_copy(
                    update={"missing": [], "ready_to_write": True}
                ),
                "downgrade_reason": "；".join(issues),
                "reasoning": (
                    f"{brief.reasoning}；题型已降级为只解读官方来源的发布分析，"
                    "不扩写实测或效果结论。"
                ),
            }
        )
        return downgraded, issues
    return brief.model_copy(update={"evidence_contract": contract}), []

