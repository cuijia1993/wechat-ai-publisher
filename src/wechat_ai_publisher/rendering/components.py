from __future__ import annotations

import html

from wechat_ai_publisher.domain.models import Topic, VisualBlock, VisualPlan
from wechat_ai_publisher.rendering.theme import VisualTheme


def render_topic_card(topic: Topic, theme: VisualTheme) -> str:
    colors = theme.colors
    return (
        f'<section style="margin:4px 0 24px;padding:20px 18px;background-color:{colors.navy};'
        'border-radius:10px;">'
        f'<p style="margin:0 0 8px;color:{colors.teal};font-size:13px;font-weight:bold;'
        'letter-spacing:0.08em;">先说结论</p>'
        f'<p style="margin:0;color:{colors.white};font-size:17px;line-height:1.75;'
        f'font-weight:bold;">{html.escape(topic.core_conclusion)}</p></section>'
    )


def _key_point(block: VisualBlock, theme: VisualTheme) -> str:
    colors = theme.colors
    items = "".join(
        f'<p style="margin:7px 0;color:{colors.white};font-size:15px;line-height:1.7;">'
        f'<span style="color:{colors.teal};font-weight:bold;">✓</span> {html.escape(item)}</p>'
        for item in block.items
    )
    return (
        f'<section style="margin:22px 0;padding:20px 18px;background-color:{colors.navy};'
        'border-radius:10px;">'
        f'<p style="margin:0 0 8px;color:{colors.teal};font-size:13px;font-weight:bold;'
        'letter-spacing:0.08em;">核心结论</p>'
        f'<p style="margin:0 0 8px;color:{colors.white};font-size:17px;font-weight:bold;">'
        f"{html.escape(block.title)}</p>"
        f'<p style="margin:0;color:{colors.white};font-size:14px;line-height:1.7;">'
        f"{html.escape(block.description)}</p>{items}</section>"
    )


def _flowchart(block: VisualBlock, theme: VisualTheme) -> str:
    colors = theme.colors
    rows: list[str] = []
    for index, item in enumerate(block.items, start=1):
        rows.append(
            "<tr>"
            f'<td style="width:38px;padding:8px 6px;vertical-align:top;">'
            f'<span style="display:inline-block;width:26px;height:26px;line-height:26px;'
            f'text-align:center;background-color:{colors.teal};color:{colors.white};'
            f'border-radius:13px;font-size:13px;font-weight:bold;">{index}</span></td>'
            f'<td style="padding:8px 6px;color:{colors.text};font-size:15px;line-height:1.7;'
            f'border-bottom:1px solid {colors.border};">{html.escape(item)}</td>'
            "</tr>"
        )
    return (
        f'<section style="margin:22px 0;padding:16px;background-color:{colors.surface};'
        'border-radius:10px;">'
        f'<p style="margin:0 0 10px;color:{colors.navy};font-size:17px;font-weight:bold;">'
        f"{html.escape(block.title)}</p>"
        f'<table style="width:100%;border-collapse:collapse;">{"".join(rows)}</table></section>'
    )


def render_visual_block(block: VisualBlock, theme: VisualTheme) -> str:
    if block.kind == "flowchart":
        return _flowchart(block, theme)
    return _key_point(block, theme)


def render_visual_blocks(plan: VisualPlan, theme: VisualTheme) -> dict[str, str]:
    rendered: dict[str, str] = {}
    for block in plan.blocks:
        rendered[block.anchor] = rendered.get(block.anchor, "") + render_visual_block(block, theme)
    return rendered


def inject_blocks(markdown_source: str, blocks: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Return unchanged Markdown and block map; formatter injects after matching headings."""
    return markdown_source, blocks

