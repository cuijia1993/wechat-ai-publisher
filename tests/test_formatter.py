from pathlib import Path

from wechat_ai_publisher.rendering.formatter import WechatFormatter
from wechat_ai_publisher.rendering.sanitize import sanitize_wechat_html, validate_wechat_html


ROOT = Path(__file__).resolve().parents[1]


def test_formatter_adds_inline_styles_and_preview_shell():
    formatter = WechatFormatter(ROOT / "templates" / "article.html")

    body = formatter.render_body("## 标题\n\n正文内容。\n\n```java\nclass Demo {}\n```")
    preview = formatter.render_preview("文章标题", "## 标题\n\n正文内容。")

    assert 'style="font-size:20px' in body
    assert "font-family:Menlo,Consolas,monospace" in body
    assert "<br>" not in body
    assert "<title>文章标题</title>" in preview
    assert "{{ content }}" not in preview
    assert "{{ page_style }}" not in preview


def test_local_images_only_returns_unuploaded_paths():
    formatter = WechatFormatter(ROOT / "templates" / "article.html")
    content = '<img src="assets/a.png" alt="a"><img src="https://mmbiz.qpic.cn/b.jpg" alt="b">'

    assert formatter.local_images(content) == [Path("assets/a.png")]


def test_formatter_preserves_code_indentation_and_sanitizes_incompatible_html():
    formatter = WechatFormatter(ROOT / "templates" / "article.html")
    body = formatter.render_body("```java\nclass Demo {\n  void run() {}\n}\n```")

    assert "&nbsp;&nbsp;void run()" in body
    unsafe = '<style>.x{}</style><script>alert(1)</script><p class="x">安全内容</p><svg></svg>'
    cleaned = sanitize_wechat_html(unsafe)
    assert cleaned == "<p>安全内容</p>"
    assert validate_wechat_html(cleaned) == []
    assert validate_wechat_html(unsafe)

