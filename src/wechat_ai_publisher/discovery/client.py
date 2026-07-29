from __future__ import annotations

import hashlib
import html
import re
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx

from wechat_ai_publisher.config import SourcesConfig
from wechat_ai_publisher.domain.models import DiscoveryBatch, SourceSignal

TAG_PATTERN = re.compile(r"<[^>]+>")


def _text(value: str | None, limit: int = 2000) -> str:
    cleaned = TAG_PATTERN.sub(" ", html.unescape(value or ""))
    return re.sub(r"\s+", " ", cleaned).strip()[:limit]


def _date(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _id(source_type: str, url: str) -> str:
    return f"{source_type}-{hashlib.sha256(url.encode()).hexdigest()[:16]}"


class DiscoveryClient:
    def __init__(self, config: SourcesConfig, *, http: httpx.Client | None = None):
        self.config = config
        self.http = http or httpx.Client(timeout=config.timeout_seconds, follow_redirects=True)

    def _score(self, title: str, summary: str, published_at: datetime) -> tuple[float, list[str]]:
        title_text = title.lower()
        summary_text = summary.lower()
        title_tags = [
            keyword
            for keyword in self.config.include_keywords
            if keyword.lower() in title_text
        ]
        summary_tags = [
            keyword
            for keyword in self.config.include_keywords
            if keyword not in title_tags and keyword.lower() in summary_text
        ]
        tags = [*title_tags, *summary_tags]
        age_days = max((datetime.now(UTC) - published_at).days, 0)
        recency = max(0, self.config.lookback_days - age_days) / max(self.config.lookback_days, 1)
        return len(title_tags) * 10 + len(summary_tags) * 2 + recency * 5, tags

    def fetch_rss(self, name: str, url: str) -> list[SourceSignal]:
        response = self.http.get(url)
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        nodes = root.findall(".//item")
        atom = False
        if not nodes:
            nodes = root.findall(".//{*}entry")
            atom = True
        signals: list[SourceSignal] = []
        cutoff = datetime.now(UTC) - timedelta(days=self.config.lookback_days)
        for node in nodes[: self.config.max_items_per_source]:
            title = _text(node.findtext("{*}title") if atom else node.findtext("title"))
            if atom:
                link_node = node.find("{*}link")
                link = link_node.get("href", "") if link_node is not None else ""
                summary = _text(node.findtext("{*}summary") or node.findtext("{*}content"))
                published = _date(node.findtext("{*}published") or node.findtext("{*}updated"))
            else:
                link = _text(node.findtext("link"))
                summary = _text(node.findtext("description"))
                published = _date(node.findtext("pubDate"))
            if not title or not link or published < cutoff:
                continue
            score, tags = self._score(title, summary, published)
            signals.append(
                SourceSignal(
                    id=_id("rss", link),
                    source_name=name,
                    source_type="rss",
                    title=title,
                    url=link,
                    summary=summary,
                    published_at=published,
                    score=score,
                    tags=tags,
                )
            )
        return signals

    def fetch_github(self, name: str, repo: str) -> list[SourceSignal]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.config.github_token:
            headers["Authorization"] = f"Bearer {self.config.github_token}"
        response = self.http.get(
            f"https://api.github.com/repos/{repo}/releases",
            params={"per_page": self.config.max_items_per_source},
            headers=headers,
        )
        response.raise_for_status()
        cutoff = datetime.now(UTC) - timedelta(days=self.config.lookback_days)
        signals: list[SourceSignal] = []
        for release in response.json():
            published = _date(release.get("published_at") or release.get("created_at"))
            if release.get("draft") or published < cutoff:
                continue
            title = _text(release.get("name") or release.get("tag_name"))
            url = str(release.get("html_url") or "")
            summary = _text(release.get("body"))
            if not title or not url:
                continue
            score, tags = self._score(title, summary, published)
            signals.append(
                SourceSignal(
                    id=_id("github", url),
                    source_name=name,
                    source_type="github",
                    title=title,
                    url=url,
                    summary=summary,
                    published_at=published,
                    score=score + 2,
                    tags=tags,
                )
            )
        return signals

    def discover(self, batch_id: str) -> DiscoveryBatch:
        signals: dict[str, SourceSignal] = {}
        errors: list[str] = []
        for source in self.config.rss:
            if not source.enabled:
                continue
            try:
                for signal in self.fetch_rss(source.name, source.url):
                    signals[signal.id] = signal
            except Exception as exc:
                errors.append(f"RSS {source.name}: {exc}")
        for source in self.config.github:
            if not source.enabled:
                continue
            try:
                for signal in self.fetch_github(source.name, source.repo):
                    signals[signal.id] = signal
            except Exception as exc:
                errors.append(f"GitHub {source.name}: {exc}")
        ordered = sorted(signals.values(), key=lambda item: (item.score, item.published_at), reverse=True)
        return DiscoveryBatch(batch_id=batch_id, signals=ordered, errors=errors)

