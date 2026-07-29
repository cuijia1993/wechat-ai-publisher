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
        author="智效进化社",
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


def test_knowledge_worker_article_requires_story_example_and_twist():
    broad_topic = topic()
    broad_topic.audience_scope = "knowledge_worker"
    broad_topic.title_angle = "problem_first"

    result = QualityGate(QualityConfig()).check(article(VALID_MARKDOWN), broad_topic)

    assert not result.passed
    assert "missing_story_elements" in {item.code for item in result.findings}

