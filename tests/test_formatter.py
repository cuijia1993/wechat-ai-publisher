from pathlib import Path

from wechat_ai_publisher.rendering.formatter import WechatFormatter
from wechat_ai_publisher.rendering.sanitize import sanitize_wechat_html, validate_wechat_html


ROOT = Path(__file__).resolve().parents[1]


def test_formatter_adds_inline_styles_and_preview_shell():
    formatter = WechatFormatter(ROOT / "templates" / "article.html")

    body = formatter.render_body("# 文章标题\n\n开头结论。\n\n## 标题\n\n正文内容。\n\n```java\nclass Demo {}\n```")
    preview = formatter.render_preview("文章标题", "## 标题\n\n正文内容。")

    assert 'style="font-size:20px' in body
    assert "01 /" in body
    assert "border-left:4px" not in body
    assert "background-color:#0B1F3A" in body
    assert "font-family:Menlo,Consolas,monospace" in body
    assert "<br>" not in body
    assert "<title>文章标题</title>" in preview
    assert "{{ content }}" not in preview
    assert "{{ page_style }}" not in preview


def test_formatter_renders_long_ordered_list_as_native_checklist():
    formatter = WechatFormatter(ROOT / "templates" / "article.html")

    body = formatter.render_body(
        "# 标题\n\n开头。\n\n"
        "1. 网络必须断开\n"
        "2. 账号限制权限\n"
        "3. 保留操作日志\n"
        "4. 准备停止入口"
    )

    assert "border-radius:14px" in body
    assert "background-color:#F4F8F8" in body
    assert "<table" in body
    assert "<img" not in body
    assert "网络必须断开" in body


def test_formatter_renders_references_as_numbered_list_instead_of_table():
    formatter = WechatFormatter(ROOT / "templates" / "article.html")

    body = formatter.render_body(
        "# 标题\n\n开头。\n\n"
        "### 参考资料\n\n"
        "1. [资料一](https://example.com/1)，来源一。\n"
        "2. [资料二](https://example.com/2)，来源二。\n"
        "3. [资料三](https://example.com/3)，来源三。"
    )

    references = body[body.index("参考资料") :]
    assert "<table" not in references
    assert ">1.</span>" in references
    assert "资料三" in references


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

