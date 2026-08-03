from wechat_ai_publisher.config import QualityConfig
from wechat_ai_publisher.domain.models import (
    Article,
    ClaimRequirement,
    EvidenceContract,
    EvidenceItem,
    Source,
    Topic,
)
from wechat_ai_publisher.quality.gates import QualityGate


def topic(verified: bool = True) -> Topic:
    return Topic(
        id="test",
        title="测试",
        category="案例",
        target_reader="Java 工程师",
        reader_problem="验证生成内容",
        core_conclusion="先验证后采用",
        required_evidence=["运行记录"],
        verification_records=["pytest 运行通过"] if verified else [],
        audience_scope="specialist",
    )


def article(markdown: str) -> Article:
    return Article(
        topic_id="test",
        title="一套可复现的 Java AI 验证流程",
        digest="从行为边界、测试断言和人工检查三个方面验证生成结果。",
        markdown=markdown,
        author="智效进化论",
    )


VALID_MARKDOWN = """# 一套可复现的 Java AI 验证流程

## 具体问题
生成代码看似完整，但业务边界和异常分支仍然需要检查。我们先明确输入与预期行为，再生成候选实现。

## 工作流设计
第一步定义边界，第二步生成候选代码，第三步执行独立检查。每一步都保留输入和输出，方便定位错误。

## 操作过程
示例使用自建 Demo，不包含真实业务数据。检查正常输入、空值、重复请求和依赖失败等不同分支。

## 人工确认
人工核对断言是否验证业务结果，而不是只验证方法被调用。对于无法确认的假设，停止合并并补充证据。

## 可复制模板
根据行为边界生成候选实现，逐项列出依据、假设、失败条件和验证方法，不要虚构任何运行结果。
"""


def test_valid_article_passes():
    result = QualityGate(QualityConfig()).check(article(VALID_MARKDOWN), topic())

    assert result.passed
    assert result.findings == []


def test_secret_and_unverified_claim_are_blocked():
    unsafe = VALID_MARKDOWN + "\n实测提升 30%，api_key=sk-abcdefghijklmnop"
    result = QualityGate(QualityConfig()).check(article(unsafe), topic(verified=False))

    assert not result.passed
    assert {"sensitive_data", "unverified_claim"} <= {item.code for item in result.findings}


def test_version_claim_requires_source_and_duplicate_title_is_blocked():
    versioned = article(VALID_MARKDOWN + "\n\nSpring AI 2.0 正式发布。")
    result = QualityGate(QualityConfig()).check(
        versioned,
        topic(),
        historical_titles=[versioned.title],
    )

    assert not result.passed
    assert {"version_without_source", "duplicate_title"} <= {item.code for item in result.findings}


def test_valid_source_date_allows_version_information():
    sourced_topic = topic()
    sourced_topic.sources = [
        Source(title="Official release", url="https://example.com/release", accessed_at="2026-07-27")
    ]
    versioned = article(VALID_MARKDOWN + "\n\nSpring AI 2.0 正式发布。")

    result = QualityGate(QualityConfig()).check(versioned, sourced_topic)

    assert result.passed


def test_runtime_claim_requires_runtime_evidence_in_contract():
    contracted_topic = topic()
    contracted_topic.evidence_contract = EvidenceContract(
        items=[
            EvidenceItem(
                id="official",
                kind="official_source",
                description="官方 Release",
                source_url="https://example.com/release",
                verified=True,
            )
        ],
        claims=[
            ClaimRequirement(
                id="release",
                claim="官方发布了新版本",
                required_kinds=["official_source"],
                evidence_refs=["official"],
                supported=True,
            )
        ],
        ready_to_write=True,
    )
    claimed = article(VALID_MARKDOWN + "\n\n## 实战结果\n\n我们已经跑通并验证了整条升级链路。")

    result = QualityGate(QualityConfig()).check(claimed, contracted_topic)

    assert not result.passed
    assert "unsupported_runtime_claim" in {item.code for item in result.findings}


def test_demo_article_is_never_publishable():
    demo = article(VALID_MARKDOWN).model_copy(update={"publication_status": "demo"})

    result = QualityGate(QualityConfig()).check(demo, topic())

    assert result.passed
    assert not result.publishable
    assert "demo_only" in {item.code for item in result.findings}


def test_heading_only_candidate_fails_content_density():
    thin = article(
        "# 空洞文章\n\n## 问题\n一句话。\n\n## 方案\n一句话。\n\n"
        "## 结果\n一句话。\n\n## 边界\n一句话。\n"
    )

    result = QualityGate(QualityConfig()).check(thin, topic())

    assert not result.passed
    assert "insufficient_content_density" in {item.code for item in result.findings}


def test_mainstream_topic_rejects_specialist_first_title():
    mainstream_topic = topic()
    mainstream_topic.audience_scope = "knowledge_worker"
    mainstream_topic.title_angle = "tool_first"
    narrow = article(VALID_MARKDOWN).model_copy(
        update={"title": "Spring AI 2.0.0 ChatMemoryRepository 迁移细节"}
    )

    result = QualityGate(QualityConfig()).check(narrow, mainstream_topic)

    assert not result.passed
    assert "narrow_specialist_title" in {item.code for item in result.findings}


def test_mainstream_title_must_contain_primary_search_keyword():
    mainstream_topic = topic()
    mainstream_topic.audience_scope = "knowledge_worker"
    mainstream_topic.title_angle = "problem_first"
    mainstream_topic.primary_search_keyword = "AI 专属卡"

    result = QualityGate(QualityConfig()).check(
        article(VALID_MARKDOWN),
        mainstream_topic,
    )

    assert not result.passed
    assert "search_keyword_missing_from_title" in {
        item.code for item in result.findings
    }


def test_knowledge_worker_guide_requires_example_and_twist_but_not_scene():
    broad_topic = topic()
    broad_topic.audience_scope = "knowledge_worker"
    broad_topic.title_angle = "problem_first"
    broad_topic.primary_search_keyword = "Java AI"
    broad_topic.content_type = "workplace_guide"
    abstract_markdown = (
        VALID_MARKDOWN.replace("输入", "材料")
        .replace("输出", "结果")
        .replace("示例", "案例")
        .replace("错误", "偏差")
        .replace("失败", "异常")
    )

    result = QualityGate(QualityConfig()).check(article(abstract_markdown), broad_topic)

    assert not result.passed
    assert "missing_example_elements" in {item.code for item in result.findings}
    assert "人物与时间场景" not in "\n".join(
        item.message for item in result.findings
    )


def test_incident_review_does_not_require_fictional_story_or_input_output():
    broad_topic = topic()
    broad_topic.audience_scope = "knowledge_worker"
    broad_topic.title_angle = "problem_first"
    broad_topic.primary_search_keyword = "Java AI"
    broad_topic.content_type = "incident_review"

    result = QualityGate(QualityConfig()).check(article(VALID_MARKDOWN), broad_topic)

    assert result.passed
    assert "missing_example_elements" not in {
        item.code for item in result.findings
    }


def test_life_idea_does_not_require_a_failure_twist():
    broad_topic = topic()
    broad_topic.audience_scope = "broad_public"
    broad_topic.title_angle = "problem_first"
    broad_topic.primary_search_keyword = "Java AI"
    broad_topic.content_type = "life_idea"
    without_twist = (
        VALID_MARKDOWN.replace("失败", "风险")
        .replace("错误", "偏差")
        .replace("但", "同时")
    )

    result = QualityGate(QualityConfig()).check(article(without_twist), broad_topic)

    assert result.passed
    assert "missing_example_elements" not in {
        item.code for item in result.findings
    }


def test_workplace_guide_accepts_an_explicit_accident_as_twist():
    broad_topic = topic()
    broad_topic.audience_scope = "knowledge_worker"
    broad_topic.title_angle = "problem_first"
    broad_topic.primary_search_keyword = "Java AI"
    broad_topic.content_type = "workplace_guide"
    with_accident = (
        VALID_MARKDOWN.replace("失败", "风险")
        .replace("错误", "偏差")
        .replace("但", "同时")
        + "\n\n执行过程中出现意外，需要人工确认后再采用。"
    )

    result = QualityGate(QualityConfig()).check(article(with_accident), broad_topic)

    assert result.passed


def test_template_style_is_reported_as_warning_without_blocking():
    templated = article(
        """# 一套可复现的 Java AI 验证流程

周四早上，小林打开电脑开始检查结果。以下是虚构组合场景，用来说明常见问题，但不代表真实个案。

## 第一个问题：输入不完整
输入缺少业务边界时，生成结果看起来完整，却可能遗漏真正需要处理的异常。团队需要回到原始需求，确认哪些条件不能由模型猜测。

## 第二个问题：检查不独立
问题是，只看生成结果无法判断实现是否可靠。更稳妥的做法是准备独立断言，覆盖正常输入、空值和重复请求。

## 第三个问题：责任不清
真正重要的是保留人工确认。输出可以作为候选实现，但合并前仍要核对依据、失败条件和无法验证的假设。

## 发布前确认
团队还要记录检查依据、执行人员和最终决定。无法确认的信息应明确留空，不能因为文章结构完整就把推测写成事实，也不能省略适用范围和停止条件。
"""
    )

    result = QualityGate(QualityConfig()).check(templated, topic())
    codes = {item.code for item in result.findings}

    assert result.passed
    assert {
        "template_numbered_headings",
        "template_fictional_opening",
        "repetitive_transitions",
    } <= codes
    assert all(item.severity == "warning" for item in result.findings)

