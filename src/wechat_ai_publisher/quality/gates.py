from __future__ import annotations

import re
from datetime import date

from wechat_ai_publisher.config import QualityConfig
from wechat_ai_publisher.domain.models import Article, GateFinding, GateResult, Topic
from wechat_ai_publisher.topic.audit import SPECIALIST_TITLE, contains_search_keyword
from wechat_ai_publisher.topic.selector import title_similarity

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)(?:api[_-]?key|app[_-]?secret|token|password)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
]
PLACEHOLDER_PATTERNS = [
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"待补充|待完善|这里插入|AI生成说明"),
    re.compile(r"作为(?:一个)?AI|as an ai", re.IGNORECASE),
]
CLAIM_PATTERN = re.compile(r"实测|提升|降低|覆盖率|准确率|\d+(?:\.\d+)?%")
VERSION_PATTERN = re.compile(r"\b(?:v?\d+\.\d+(?:\.\d+)?|GA|Release)\b|版本|正式发布", re.IGNORECASE)
RUNTIME_ASSERTION_PATTERN = re.compile(
    r"实测|跑通|验证了|测试通过|运行结果|压测|QPS|性能(?:提升|降低)|"
    r"(?:提升|降低)了?\s*\d+(?:\.\d+)?%"
)
RUNTIME_EVIDENCE_KINDS = {"runtime_log", "benchmark", "manual_verification"}
EXAMPLE_PATTERN = re.compile(r"例如|比如|示例|输入|输出|原文|改写前|改写后|提示词|清单")
TWIST_PATTERN = re.compile(r"却|没想到|失败|遗漏|返工|出错|错误|不准确|人工修改|最后发现")
EXAMPLE_REQUIRED_CONTENT_TYPES = {
    "workplace_guide",
    "life_idea",
    "team_workflow",
    "case_study",
    "tutorial",
    "experiment",
    "comparison",
}
NUMBERED_HEADING_PATTERN = re.compile(
    r"^#{2,3}\s+第[一二三四五六七八九十\d]+(?:个|步|种|点|项|招|条)",
    re.MULTILINE,
)
TEMPLATE_SCENE_PATTERN = re.compile(
    r"(?:周[一二三四五六日]|早上|上午|下午|晚上|下班)"
    r"[\s\S]{0,80}?小[\u4e00-\u9fff]"
)
GENERIC_TRANSITION_PATTERN = re.compile(
    r"问题是|更稳妥的做法是|值得注意的是|真正重要的是|真正危险的是"
)


class QualityGate:
    def __init__(self, config: QualityConfig):
        self.config = config

    def check(
        self,
        article: Article,
        topic: Topic,
        *,
        historical_titles: list[str] | None = None,
    ) -> GateResult:
        findings: list[GateFinding] = []
        text = f"{article.title}\n{article.digest}\n{article.markdown}"
        publishable = article.publication_status == "candidate"

        if not article.title.strip() or len(article.title) > 64:
            findings.append(GateFinding(code="title_length", message="标题必须为 1～64 个字符"))
        if topic.audience_scope != "specialist" and (
            topic.title_angle != "problem_first"
            or SPECIALIST_TITLE.search(article.title)
        ):
            findings.append(
                GateFinding(
                    code="narrow_specialist_title",
                    message="大众与知识工作者选题必须以普遍问题开场，标题不能堆叠版本号、配置项或代码标识符",
                )
            )
        if topic.audience_scope != "specialist":
            if not topic.primary_search_keyword.strip():
                findings.append(
                    GateFinding(
                        code="missing_primary_search_keyword",
                        message="大众选题必须设置主搜索词，兼顾新号的搜一搜入口",
                    )
                )
            elif not contains_search_keyword(
                article.title, topic.primary_search_keyword
            ):
                findings.append(
                    GateFinding(
                        code="search_keyword_missing_from_title",
                        message=(
                            "标题没有包含主搜索词："
                            f"{topic.primary_search_keyword}"
                        ),
                    )
                )
        if not article.digest.strip() or len(article.digest) > 120:
            findings.append(GateFinding(code="digest_length", message="摘要必须为 1～120 个字符"))
        if len(article.markdown.strip()) < 200:
            findings.append(GateFinding(code="article_too_short", message="正文过短，无法形成完整公众号文章"))
        content_without_code = re.sub(r"```.*?```", "", article.markdown, flags=re.DOTALL)
        content_without_headings = re.sub(
            r"^#{1,6}\s+.*$", "", content_without_code, flags=re.MULTILINE
        )
        compact_content = re.sub(
            r"[\s#>*_`\-\[\]()]|https?://\S+", "", content_without_headings
        )
        substantive_paragraphs = [
            paragraph
            for paragraph in re.split(r"\n\s*\n", content_without_headings)
            if len(re.sub(r"\s+", "", paragraph)) >= 25
        ]
        if article.publication_status == "candidate" and (
            len(compact_content) < 220 or len(substantive_paragraphs) < 4
        ):
            findings.append(
                GateFinding(
                    code="insufficient_content_density",
                    message="正文缺少足够的实质段落，不能仅靠标题、清单或视觉组件形成文章",
                )
            )
        if (
            topic.audience_scope in {"broad_public", "knowledge_worker"}
            and topic.content_type in EXAMPLE_REQUIRED_CONTENT_TYPES
        ):
            missing_example_parts = [
                name
                for name, pattern in (
                    ("具体输入输出示例", EXAMPLE_PATTERN),
                    ("失败、意外或人工修改", TWIST_PATTERN),
                )
                if not pattern.search(article.markdown)
            ]
            if missing_example_parts:
                findings.append(
                    GateFinding(
                        code="missing_example_elements",
                        message=(
                            "教程与案例文章缺少必要要素："
                            f"{'、'.join(missing_example_parts)}"
                        ),
                    )
                )

        headings = re.findall(r"^#{2,3}\s+(.+)$", article.markdown, re.MULTILINE)
        if len(headings) < 3:
            findings.append(GateFinding(code="missing_structure", message="正文至少需要 3 个二、三级章节"))

        numbered_headings = NUMBERED_HEADING_PATTERN.findall(article.markdown)
        if len(numbered_headings) >= 3:
            findings.append(
                GateFinding(
                    code="template_numbered_headings",
                    message="连续使用多个编号式小标题，建议合并或改为描述实际内容的标题",
                    severity="warning",
                )
            )

        opening = content_without_code[:350]
        if (
            TEMPLATE_SCENE_PATTERN.search(opening)
            and re.search(r"虚构|组合场景", article.markdown)
        ):
            findings.append(
                GateFinding(
                    code="template_fictional_opening",
                    message="检测到模板化虚构人物开场；能用真实事实讲清时不要新增“小林/小王”",
                    severity="warning",
                )
            )

        if len(GENERIC_TRANSITION_PATTERN.findall(article.markdown)) >= 3:
            findings.append(
                GateFinding(
                    code="repetitive_transitions",
                    message="正文重复使用总结式过渡语，建议改成事实、动作或直接判断",
                    severity="warning",
                )
            )

        for term in self.config.forbidden_terms:
            if term in text:
                findings.append(GateFinding(code="forbidden_term", message=f"包含禁用表达：{term}"))

        patterns = [re.compile(value, re.IGNORECASE) for value in self.config.internal_patterns]
        for pattern in [*SECRET_PATTERNS, *patterns]:
            if pattern.search(text):
                findings.append(GateFinding(code="sensitive_data", message=f"疑似包含敏感信息：{pattern.pattern}"))

        for pattern in PLACEHOLDER_PATTERNS:
            if pattern.search(text):
                findings.append(GateFinding(code="ai_placeholder", message="正文包含占位符或 AI 生成痕迹"))
                break

        contract = topic.evidence_contract
        if contract:
            if not contract.ready_to_write or contract.missing or not contract.claims:
                findings.append(
                    GateFinding(
                        code="incomplete_evidence_contract",
                        message="选题证据契约未完成，禁止进入发布候选",
                    )
                )
            verified_items = {
                item.id: item for item in contract.items if item.verified
            }
            for claim in contract.claims:
                referenced = [
                    verified_items[ref]
                    for ref in claim.evidence_refs
                    if ref in verified_items
                ]
                if (
                    not claim.supported
                    or not referenced
                    or not set(claim.required_kinds)
                    & {item.kind for item in referenced}
                ):
                    findings.append(
                        GateFinding(
                            code="broken_evidence_contract",
                            message=f"核心结论没有绑定所需证据：{claim.claim}",
                        )
                    )
            available_kinds = {item.kind for item in verified_items.values()}
            if RUNTIME_ASSERTION_PATTERN.search(text) and not (
                available_kinds & RUNTIME_EVIDENCE_KINDS
            ):
                findings.append(
                    GateFinding(
                        code="unsupported_runtime_claim",
                        message="正文包含实战、跑通或效果结论，但证据契约中没有运行记录或基准测试",
                    )
                )
        elif self.config.require_verification_for_claims and CLAIM_PATTERN.search(text):
            if not topic.verification_records:
                findings.append(
                    GateFinding(code="unverified_claim", message="正文包含实测或量化结论，但选题没有验证记录")
                )

        if self.config.require_sources and ("http://" in text or "https://" in text) and not topic.sources:
            findings.append(GateFinding(code="missing_sources", message="正文包含外部链接，但选题没有结构化来源记录"))

        if self.config.require_sources and VERSION_PATTERN.search(text) and not topic.sources:
            findings.append(GateFinding(code="version_without_source", message="正文包含版本或发布信息，但没有结构化来源"))

        for source in topic.sources:
            try:
                date.fromisoformat(source.accessed_at)
            except ValueError:
                findings.append(
                    GateFinding(code="invalid_source_date", message=f"来源核验日期格式无效：{source.title}")
                )

        if historical_titles and any(
            title_similarity(article.title, historical) >= 0.86 for historical in historical_titles
        ):
            findings.append(GateFinding(code="duplicate_title", message="标题与历史草稿或已发布文章高度重复"))

        if not publishable:
            findings.append(
                GateFinding(
                    code="demo_only",
                    message="演示模型产物只能用于流程验收，不能进入真实发布",
                    severity="warning",
                )
            )

        return GateResult(
            passed=not any(item.severity == "error" for item in findings),
            publishable=publishable,
            findings=findings,
        )

