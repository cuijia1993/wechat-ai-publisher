from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from wechat_ai_publisher.wechat.client import WechatClient


EARLIEST_DETAIL_DATE = date(2025, 11, 1)
METRIC_FIELDS = (
    "read_user",
    "share_user",
    "zaikan_user",
    "like_user",
    "comment_count",
    "collection_user",
    "praise_money",
    "read_subscribe_user",
)


def parse_publish_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("日期必须使用 YYYY-MM-DD 格式") from exc
    yesterday = datetime.now().astimezone().date() - timedelta(days=1)
    if parsed < EARLIEST_DETAIL_DATE:
        raise ValueError("详细数据接口仅支持 2025-11-01 及之后的发表日期")
    if parsed > yesterday:
        raise ValueError("微信统计最多只能查询到昨天")
    return parsed


def recent_publish_dates(days: int) -> list[date]:
    if not 1 <= days <= 365:
        raise ValueError("days 必须在 1 到 365 之间")
    yesterday = datetime.now().astimezone().date() - timedelta(days=1)
    start = max(EARLIEST_DETAIL_DATE, yesterday - timedelta(days=days - 1))
    return [start + timedelta(days=offset) for offset in range((yesterday - start).days + 1)]


class ArticleAnalyticsStore:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def save(self, publish_date: date, payload: dict[str, Any]) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{publish_date.isoformat()}.json"
        result = {
            "query_date": publish_date.isoformat(),
            "fetched_at": datetime.now(UTC).isoformat(),
            "payload": payload,
        }
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_recent(self, days: int) -> list[dict[str, Any]]:
        allowed_dates = {item.isoformat() for item in recent_publish_dates(days)}
        snapshots: list[dict[str, Any]] = []
        if not self.output_dir.exists():
            return snapshots
        for path in sorted(self.output_dir.glob("*.json")):
            if path.stem in allowed_dates:
                snapshots.append(json.loads(path.read_text(encoding="utf-8")))
        return snapshots


class ArticleAnalytics:
    def __init__(self, client: WechatClient | None, store: ArticleAnalyticsStore):
        self.client = client
        self.store = store

    def fetch(self, publish_dates: list[date]) -> list[dict[str, Any]]:
        if self.client is None:
            raise ValueError("拉取微信数据需要配置公众号凭据")
        results: list[dict[str, Any]] = []
        for publish_date in publish_dates:
            payload = self.client.get_article_total_detail(publish_date.isoformat())
            path = self.store.save(publish_date, payload)
            results.append(
                {
                    "query_date": publish_date.isoformat(),
                    "article_count": len(payload["list"]),
                    "is_delay": payload.get("is_delay", False),
                    "output": str(path),
                }
            )
        return results

    def report(self, days: int) -> dict[str, Any]:
        articles: dict[str, dict[str, Any]] = {}
        snapshots = self.store.load_recent(days)
        delayed_dates: list[str] = []
        for snapshot in snapshots:
            payload = snapshot.get("payload", {})
            if payload.get("is_delay") in (True, "true"):
                delayed_dates.append(str(snapshot.get("query_date", "")))
            for article in payload.get("list", []):
                details = article.get("detail_list") or []
                if not details:
                    continue
                latest = max(details, key=lambda item: item.get("stat_date", ""))
                msgid = str(article.get("msgid", ""))
                if not msgid:
                    continue
                metrics = {field: latest.get(field, 0) for field in METRIC_FIELDS}
                metrics.update(
                    {
                        "read_delivery_rate": latest.get("read_delivery_rate", 0),
                        "read_finish_rate": latest.get("read_finish_rate", 0),
                        "read_avg_activetime": latest.get("read_avg_activetime", 0),
                    }
                )
                articles[msgid] = {
                    "msgid": msgid,
                    "title": article.get("title", ""),
                    "content_url": article.get("content_url", ""),
                    "publish_date": article.get("ref_date", ""),
                    "stat_date": latest.get("stat_date", ""),
                    **metrics,
                }

        article_list = sorted(
            articles.values(),
            key=lambda item: (item["publish_date"], item["msgid"]),
            reverse=True,
        )
        totals = {
            field: sum(float(article[field] or 0) for article in article_list)
            for field in METRIC_FIELDS
        }
        totals["praise_money_yuan"] = totals.pop("praise_money") / 100
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "days": days,
            "snapshot_count": len(snapshots),
            "article_count": len(article_list),
            "delayed_dates": delayed_dates,
            "totals": totals,
            "articles": article_list,
        }
