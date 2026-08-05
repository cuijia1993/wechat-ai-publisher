from pathlib import Path

from wechat_ai_publisher.domain.models import Article
from wechat_ai_publisher.export.draft_writer import DraftWriter, ensure_markdown_title
from wechat_ai_publisher.rendering.formatter import WechatFormatter
from wechat_ai_publisher.rendering.theme import load_theme


ROOT = Path(__file__).resolve().parents[1]


def test_ensure_markdown_title_prepends_missing_heading():
    assert ensure_markdown_title("标题", "正文第一段") == "# 标题\n\n正文第一段"


def test_ensure_markdown_title_replaces_mismatched_heading():
    assert (
        ensure_markdown_title("正确标题", "# 旧标题\n\n正文")
        == "# 正确标题\n\n正文"
    )


def test_export_writes_visible_title_into_markdown_and_html(tmp_path):
    formatter = WechatFormatter(
        ROOT / "templates" / "article.html",
        load_theme(ROOT / "config" / "themes" / "professional-minimal.yaml"),
    )
    article = Article(
        topic_id="title-export",
        title="MacBook Air 缺货要等一个月",
        digest="摘要",
        markdown="打开官网准备下单。\n\n## 原因\n\n供应紧张。",
        author="智效进化论",
    )
    outputs = DraftWriter(tmp_path, formatter).export(article, run_id="run-1")
    markdown = Path(outputs["markdown"]).read_text(encoding="utf-8")
    html = Path(outputs["html"]).read_text(encoding="utf-8")
    assert markdown.startswith("# MacBook Air 缺货要等一个月\n")
    assert "<h1" in html
    assert "MacBook Air 缺货要等一个月" in html
