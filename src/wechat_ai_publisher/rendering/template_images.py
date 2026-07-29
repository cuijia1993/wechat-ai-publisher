from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from wechat_ai_publisher.rendering.theme import VisualTheme

FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


def _font(size: int, *, bold: bool = False):
    candidates = (
        ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc"]
        if bold
        else FONT_CANDIDATES
    )
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size=size, index=0)
    return ImageFont.load_default(size=size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    current = ""
    tokens = re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_.+/-]+|\s+|[^\w\s]", text)
    truncated = False
    for token in tokens:
        if "\n" in token:
            if current:
                lines.append(current.rstrip())
                current = ""
            if len(lines) == max_lines:
                truncated = True
                break
            continue
        candidate = current + token
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current.rstrip())
            current = token.lstrip()
            if len(lines) == max_lines:
                truncated = True
                break
    if current and len(lines) < max_lines:
        lines.append(current.rstrip())
    if truncated and lines:
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_width:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines


class TemplateImageRenderer:
    def __init__(self, theme: VisualTheme):
        self.theme = theme

    def render_cover(
        self,
        *,
        title: str,
        subtitle: str,
        category: str,
        output: Path,
        brand: str = "智效进化社",
    ) -> Path:
        colors = self.theme.colors
        image = Image.new("RGB", (900, 383), colors.navy)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 18, 383), fill=colors.teal)
        draw.rounded_rectangle((650, 44, 842, 88), radius=20, fill=colors.teal)
        draw.text((746, 66), category[:12], font=_font(18, bold=True), fill=colors.white, anchor="mm")
        draw.text((72, 56), brand, font=_font(23, bold=True), fill=colors.teal_soft)

        title_font = _font(44, bold=True)
        title_lines = _wrap(draw, title, title_font, 740, 3)
        y = 115
        for line in title_lines:
            draw.text((72, y), line, font=title_font, fill=colors.white)
            y += 58

        draw.line((72, 307, 178, 307), fill=colors.teal, width=5)
        subtitle_font = _font(20)
        subtitle_lines = _wrap(draw, subtitle, subtitle_font, 650, 2)
        for line in subtitle_lines:
            draw.text((200, 294), line, font=subtitle_font, fill=colors.teal_soft)
            break

        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output, format="PNG", optimize=True)
        return output

    def render_checklist(
        self,
        *,
        title: str,
        items: list[str],
        output: Path,
        brand: str = "智效进化社",
    ) -> Path:
        colors = self.theme.colors
        item_font = _font(22)
        measure = ImageDraw.Draw(Image.new("RGB", (900, 1)))
        wrapped_items = [
            _wrap(measure, item, item_font, 720, 2) for item in items[:6]
        ]
        row_heights = [max(62, len(lines) * 30 + 20) for lines in wrapped_items]
        height = max(240, 82 + 38 + sum(row_heights) + 42)

        image = Image.new("RGB", (900, height), colors.surface)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 900, 82), fill=colors.navy)
        draw.text((48, 41), title, font=_font(30, bold=True), fill=colors.white, anchor="lm")
        y = 120
        for index, (lines, row_height) in enumerate(
            zip(wrapped_items, row_heights, strict=True), start=1
        ):
            draw.ellipse((48, y, 78, y + 30), fill=colors.teal)
            draw.text((63, y + 15), str(index), font=_font(16, bold=True), fill=colors.white, anchor="mm")
            for line_index, line in enumerate(lines):
                draw.text((98, y + line_index * 30), line, font=item_font, fill=colors.text)
            y += row_height
        draw.text((852, height - 30), brand, font=_font(16), fill=colors.muted, anchor="rm")
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output, format="PNG", optimize=True)
        return output

