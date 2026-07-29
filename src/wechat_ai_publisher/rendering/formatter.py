from __future__ import annotations

import html
import re
from pathlib import Path

import markdown

from wechat_ai_publisher.rendering.sanitize import sanitize_wechat_html
from wechat_ai_publisher.rendering.theme import VisualTheme

IMAGE_PATTERN = re.compile(r'<img\b[^>]*\bsrc="([^"]+)"[^>]*>')
CODE_PATTERN = re.compile(r"<pre><code(?:\s[^>]*)?>(.*?)</code></pre>", re.DOTALL)
LIST_PATTERN = re.compile(r"<(ul|ol)>(.*?)</\1>", re.DOTALL)
ITEM_PATTERN = re.compile(r"<li>(.*?)</li>", re.DOTALL)


class WechatFormatter:
    def __init__(self, template_path: Path, theme: VisualTheme | None = None):
        self.template = template_path.read_text(encoding="utf-8")
        self.theme = theme or VisualTheme()

    def _render_code_blocks(self, body: str) -> str:
        colors = self.theme.colors
        typography = self.theme.typography
        spacing = self.theme.spacing

        def replace(match: re.Match[str]) -> str:
            lines = match.group(1).splitlines() or [""]
            rendered: list[str] = []
            for line in lines:
                leading = len(line) - len(line.lstrip(" "))
                rendered.append("&nbsp;" * leading + line[leading:])
            code = "<br>".join(rendered)
            return (
                f'<section style="margin:{spacing.block_margin}px 0;padding:16px;'
                f'background-color:{colors.code_background};border-radius:{spacing.radius}px;'
                f'overflow-wrap:break-word;">'
                f'<p style="margin:0;color:{colors.code_text};font-size:{typography.code_size}px;'
                'line-height:1.7;font-family:Menlo,Consolas,monospace;">'
                f"{code}</p></section>"
            )

        return CODE_PATTERN.sub(replace, body)

    def _render_lists(self, body: str) -> str:
        colors = self.theme.colors
        spacing = self.theme.spacing

        def replace(match: re.Match[str]) -> str:
            ordered = match.group(1) == "ol"
            items = ITEM_PATTERN.findall(match.group(2))
            rows = []
            for index, item in enumerate(items, start=1):
                marker = f"{index}." if ordered else "•"
                rows.append(
                    f'<p style="margin:8px 0;padding-left:22px;color:{colors.text};'
                    'line-height:1.8;">'
                    f'<span style="display:inline-block;margin-left:-22px;width:22px;'
                    f'color:{colors.teal};font-weight:bold;">{marker}</span>{item}</p>'
                )
            return f'<section style="margin:{spacing.paragraph_margin}px 0;">{"".join(rows)}</section>'

        return LIST_PATTERN.sub(replace, body)

    @staticmethod
    def _inject_blocks(body: str, blocks: dict[str, str]) -> str:
        for anchor, block_html in blocks.items():
            pattern = re.compile(
                rf"(<h[23][^>]*>[^<]*{re.escape(html.escape(anchor))}[^<]*</h[23]>)",
                re.IGNORECASE,
            )
            if pattern.search(body):
                body = pattern.sub(rf"\1{block_html}", body, count=1)
            else:
                body += block_html
        return body

    def render_body(
        self,
        source: str,
        *,
        include_h1: bool = True,
        visual_blocks: dict[str, str] | None = None,
    ) -> str:
        colors = self.theme.colors
        typography = self.theme.typography
        spacing = self.theme.spacing
        body = markdown.markdown(source, extensions=["fenced_code", "tables", "sane_lists"])
        body = self._render_code_blocks(body)
        body = self._render_lists(body)
        if not include_h1:
            body = re.sub(r"<h1>.*?</h1>", "", body, count=1, flags=re.DOTALL)
        replacements = {
            "<h1>": (
                f'<h1 style="font-size:{typography.h1_size}px;line-height:1.45;'
                f'margin:{spacing.section_margin}px 0 18px;color:{colors.navy};font-weight:bold;">'
            ),
            "<h2>": (
                f'<h2 style="font-size:{typography.h2_size}px;line-height:1.55;'
                f'margin:{spacing.section_margin}px 0 14px;color:{colors.navy};font-weight:bold;'
                f'border-left:4px solid {colors.teal};padding-left:12px;">'
            ),
            "<h3>": (
                f'<h3 style="font-size:{typography.h3_size}px;line-height:1.6;'
                f'margin:24px 0 10px;color:{colors.navy_soft};font-weight:bold;">'
            ),
            "<p>": (
                f'<p style="margin:{spacing.paragraph_margin}px 0;color:{colors.text};'
                f'font-size:{typography.body_size}px;line-height:{typography.body_line_height};'
                'letter-spacing:0.02em;text-align:left;">'
            ),
            "<blockquote>": (
                f'<blockquote style="margin:{spacing.block_margin}px 0;padding:14px 16px;'
                f'background-color:{colors.surface};color:{colors.text};'
                f'border-left:4px solid {colors.teal};border-radius:{spacing.radius}px;">'
            ),
            "<code>": (
                f'<code style="color:{colors.navy_soft};background-color:{colors.surface};'
                'padding:2px 5px;border-radius:4px;font-family:Menlo,Consolas,monospace;">'
            ),
            "<strong>": f'<strong style="color:{colors.navy};font-weight:bold;">',
            "<a ": f'<a style="color:{colors.teal};text-decoration:none;" ',
            "<hr>": f'<hr style="border:0;border-top:1px solid {colors.border};margin:28px 0;">',
            "<table>": (
                f'<table style="width:100%;border-collapse:collapse;margin:{spacing.block_margin}px 0;'
                f'color:{colors.text};font-size:14px;">'
            ),
            "<th>": (
                f'<th style="border:1px solid {colors.border};padding:9px;'
                f'background-color:{colors.surface};color:{colors.navy};text-align:left;">'
            ),
            "<td>": f'<td style="border:1px solid {colors.border};padding:9px;vertical-align:top;">',
            "<img ": (
                f'<img style="display:block;max-width:100%;height:auto;margin:{spacing.block_margin}px auto;'
                f'border-radius:{spacing.radius}px;" '
            ),
        }
        for original, styled in replacements.items():
            body = body.replace(original, styled)
        body = self._inject_blocks(body, visual_blocks or {})
        return sanitize_wechat_html(body)

    def render_preview(
        self,
        title: str,
        source: str,
        *,
        prelude_html: str = "",
        visual_blocks: dict[str, str] | None = None,
    ) -> str:
        colors = self.theme.colors
        typography = self.theme.typography
        spacing = self.theme.spacing
        page_style = (
            f"max-width:677px;margin:0 auto;padding:{spacing.page_padding}px;"
            f"background-color:{colors.white};color:{colors.text};"
            f"font-size:{typography.body_size}px;line-height:{typography.body_line_height};"
        )
        content = sanitize_wechat_html(prelude_html) + self.render_body(
            source, visual_blocks=visual_blocks
        )
        return (
            self.template.replace("{{ title }}", html.escape(title))
            .replace("{{ page_style }}", page_style)
            .replace("{{ content }}", content)
        )

    @staticmethod
    def local_images(content: str) -> list[Path]:
        images: list[Path] = []
        for source in IMAGE_PATTERN.findall(content):
            if not source.startswith(("http://", "https://", "data:")):
                images.append(Path(source))
        return images

    @staticmethod
    def replace_image(content: str, original: str, uploaded_url: str) -> str:
        return content.replace(f'src="{original}"', f'src="{uploaded_url}"')

