from datetime import date, datetime, timedelta

from wechat_ai_publisher.wechat.analytics import ArticleAnalytics, ArticleAnalyticsStore


def test_fetch_saves_snapshot_and_report_uses_latest_detail(tmp_path):
    publish_date = datetime.now().astimezone().date() - timedelta(days=2)
    date_text = publish_date.isoformat()
    latest_date_text = (publish_date + timedelta(days=1)).isoformat()

    class FakeClient:
        def get_article_total_detail(self, requested_date: str):
            assert requested_date == date_text
            return {
                "list": [
                    {
                        "ref_date": date_text,
                        "msgid": "123_1",
                        "title": "测试文章",
                        "content_url": "https://example.com/article",
                        "detail_list": [
                            {"stat_date": date_text, "read_user": 10, "share_user": 1},
                            {"stat_date": latest_date_text, "read_user": 20, "share_user": 2},
                        ],
                    }
                ],
                "is_delay": False,
            }

    store = ArticleAnalyticsStore(tmp_path)
    analytics = ArticleAnalytics(FakeClient(), store)  # type: ignore[arg-type]

    result = analytics.fetch([date.fromisoformat(date_text)])
    report = analytics.report(2)

    assert result[0]["article_count"] == 1
    assert (tmp_path / f"{date_text}.json").exists()
    assert report["article_count"] == 1
    assert report["totals"]["read_user"] == 20
    assert report["totals"]["share_user"] == 2
