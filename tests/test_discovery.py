import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from wechat_ai_publisher.config import GitHubSourceConfig, RSSSourceConfig, SourcesConfig
from wechat_ai_publisher.discovery.client import DiscoveryClient
from wechat_ai_publisher.domain.models import SourceSignal
from wechat_ai_publisher.topic.selector import rank_signals


ROOT = Path(__file__).resolve().parents[1]


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

