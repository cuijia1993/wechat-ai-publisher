import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from wechat_ai_publisher.config import GitHubSourceConfig, RSSSourceConfig, SourcesConfig
from wechat_ai_publisher.discovery.client import DiscoveryClient, _date
from wechat_ai_publisher.discovery.source_fetcher import SourceFetcher
from wechat_ai_publisher.domain.models import SourceSignal
from wechat_ai_publisher.topic.selector import rank_signals


ROOT = Path(__file__).resolve().parents[1]


def test_date_parses_china_feed_formats():
    parsed = _date("2026-08-04 18:27:21  +0800")
    assert parsed.year == 2026
    assert parsed.month == 8
    assert parsed.day == 4
    assert parsed.astimezone(UTC).hour == 10


def test_discovery_normalizes_rss_and_github():
    atom = (ROOT / "tests" / "fixtures" / "rss" / "spring.atom").read_bytes()
    releases = json.loads(
        (ROOT / "tests" / "fixtures" / "github" / "releases.json").read_text(encoding="utf-8")
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "spring.test":
            return httpx.Response(200, content=atom)
        return httpx.Response(200, json=releases)

    config = SourcesConfig(
        lookback_days=3650,
        include_keywords=["java", "spring", "agent", "mcp", "security"],
        rss=[RSSSourceConfig(name="Spring", url="https://spring.test/feed")],
        github=[GitHubSourceConfig(name="Spring AI", repo="spring-projects/spring-ai")],
    )
    client = DiscoveryClient(config, http=httpx.Client(transport=httpx.MockTransport(handler)))

    batch = client.discover("batch-1")

    assert len(batch.signals) == 2
    assert {item.source_type for item in batch.signals} == {"rss", "github"}
    assert all(item.url.startswith("https://") for item in batch.signals)
    assert batch.errors == []


def test_discovery_prefers_keyword_in_title_over_summary_boilerplate():
    config = SourcesConfig(
        lookback_days=45,
        include_keywords=["health", "education", "work"],
    )
    client = DiscoveryClient(config)
    published_at = datetime.now(UTC)

    title_score, _ = client._score("Health advice from AI", "", published_at)
    boilerplate_score, _ = client._score(
        "Gemini product update",
        "Available to education plans and people at work.",
        published_at,
    )

    assert title_score > boilerplate_score


def test_rank_signals_filters_duplicate_titles():
    atom = (ROOT / "tests" / "fixtures" / "rss" / "spring.atom").read_bytes()
    config = SourcesConfig(
        lookback_days=3650,
        include_keywords=["java", "agent"],
        rss=[RSSSourceConfig(name="Spring", url="https://spring.test/feed")],
    )
    client = DiscoveryClient(
        config,
        http=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=atom))),
    )
    signal = client.discover("batch-2").signals[0]

    assert rank_signals([signal], [signal.title]) == []
    assert rank_signals([signal], ["完全不同的历史文章"])[0].id == signal.id


def test_rank_signals_prioritizes_public_impact_and_risk_topics():
    published_at = datetime(2026, 7, 29, tzinfo=UTC)
    product_update = SourceSignal(
        id="product-update",
        source_name="Example",
        source_type="rss",
        title="AI product update",
        url="https://example.com/product-update",
        summary="A new model version is available.",
        published_at=published_at,
    )
    public_impact = SourceSignal(
        id="public-impact",
        source_name="Example",
        source_type="rss",
        title="AI 裁员风险与职场避坑",
        url="https://example.com/public-impact",
        summary="分析普通人的收入影响，并提供可执行检查清单。",
        published_at=published_at,
    )

    ranked = rank_signals([product_update, public_impact], [])

    assert ranked[0].id == public_impact.id
    assert ranked[0].score > product_update.score


def test_source_fetcher_extracts_article_text_and_ignores_page_noise():
    html = """
    <html><body>
      <nav>菜单与登录入口</nav>
      <main><article>
        <h1>Official AI safety update</h1>
        <p>This official report explains a verified safety change for consumers.</p>
        <p>It also documents the scope, limitations, and concrete response process.</p>
      </article></main>
      <script>secret page state</script>
    </body></html>
    """
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "text/html; charset=utf-8"},
                text=html,
                request=request,
            )
        )
    )
    fetcher = SourceFetcher(
        SourcesConfig(min_document_chars=80),
        http=client,
        resolve_hosts=False,
    )
    candidate = SourceSignal(
        id="source",
        source_name="Official",
        source_type="rss",
        title="Official AI safety update",
        url="https://example.com/article",
        summary="Short summary",
        published_at=datetime.now(UTC),
    )

    document = fetcher.fetch(candidate)

    assert document.usable
    assert document.extraction_method == "html"
    assert "verified safety change" in document.content
    assert "菜单与登录入口" not in document.content
    assert "secret page state" not in document.content


def test_source_fetcher_rejects_challenge_page_and_private_url():
    challenge = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text="<html>Enable JavaScript and cookies to continue</html>",
                request=request,
            )
        )
    )
    config = SourcesConfig(min_document_chars=20)
    fetcher = SourceFetcher(config, http=challenge, resolve_hosts=False)
    challenged = SourceSignal(
        id="challenge",
        source_name="Official",
        source_type="rss",
        title="Challenge",
        url="https://example.com/challenge",
        summary="too short",
        published_at=datetime.now(UTC),
    )
    private = challenged.model_copy(
        update={"id": "private", "url": "http://127.0.0.1/admin"}
    )

    assert not fetcher.fetch(challenged).usable
    private_document = fetcher.fetch(private)
    assert not private_document.usable
    assert "私有或本地网络" in (private_document.error or "")

