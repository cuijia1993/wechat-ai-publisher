from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from wechat_ai_publisher.rendering.template_images import _font, _wrap
from wechat_ai_publisher.rendering.theme import ThemeColors

WIDTH = 1080
HEIGHT = 1440
MARGIN = 76
BRAND = "智效进化社"


def _canvas(*, dark: bool = False) -> tuple[Image.Image, ImageDraw.ImageDraw, ThemeColors]:
    colors = ThemeColors()
    image = Image.new("RGB", (WIDTH, HEIGHT), colors.navy if dark else colors.surface)
    return image, ImageDraw.Draw(image), colors


def _text(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    xy: tuple[int, int],
    size: int,
    color: str,
    width: int,
    lines: int = 6,
    bold: bool = False,
    spacing: int = 14,
) -> int:
    font = _font(size, bold=bold)
    wrapped = _wrap(draw, text, font, width, lines)
    y = xy[1]
    line_height = size + spacing
    for line in wrapped:
        draw.text((xy[0], y), line, font=font, fill=color)
        y += line_height
    return y


def _header(
    draw: ImageDraw.ImageDraw,
    colors: ThemeColors,
    *,
    number: str,
    title: str,
    subtitle: str,
) -> int:
    draw.rounded_rectangle((MARGIN, 62, MARGIN + 96, 110), radius=24, fill=colors.teal)
    draw.text(
        (MARGIN + 48, 86),
        number,
        font=_font(24, bold=True),
        fill=colors.white,
        anchor="mm",
    )
    y = _text(
        draw,
        title,
        xy=(MARGIN, 155),
        size=52,
        color=colors.navy,
        width=WIDTH - MARGIN * 2,
        lines=2,
        bold=True,
        spacing=18,
    )
    return _text(
        draw,
        subtitle,
        xy=(MARGIN, y + 14),
        size=28,
        color=colors.muted,
        width=WIDTH - MARGIN * 2,
        lines=2,
        spacing=12,
    )


def _footer(draw: ImageDraw.ImageDraw, colors: ThemeColors, page: int) -> None:
    draw.line((MARGIN, 1350, WIDTH - MARGIN, 1350), fill=colors.border, width=2)
    draw.text((MARGIN, 1384), BRAND, font=_font(22, bold=True), fill=colors.teal)
    draw.text(
        (WIDTH - MARGIN, 1384),
        f"{page}/7",
        font=_font(22),
        fill=colors.muted,
        anchor="ra",
    )


def _card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    colors: ThemeColors,
    *,
    fill: str | None = None,
) -> None:
    draw.rounded_rectangle(
        box,
        radius=30,
        fill=fill or colors.white,
        outline=colors.border,
        width=2,
    )


def _render_cover(output: Path) -> None:
    image, draw, colors = _canvas(dark=True)
    draw.rounded_rectangle((MARGIN, 70, MARGIN + 220, 122), radius=26, fill=colors.teal)
    draw.text(
        (MARGIN + 110, 96),
        "AI 图像轻教程",
        font=_font(23, bold=True),
        fill=colors.white,
        anchor="mm",
    )
    _text(
        draw,
        "AI 做封面",
        xy=(MARGIN, 190),
        size=82,
        color=colors.white,
        width=WIDTH - MARGIN * 2,
        lines=1,
        bold=True,
    )
    _text(
        draw,
        "别只写“高级感”",
        xy=(MARGIN, 302),
        size=64,
        color=colors.teal_soft,
        width=WIDTH - MARGIN * 2,
        lines=1,
        bold=True,
    )
    _text(
        draw,
        "一套可以反复修改的提示词结构",
        xy=(MARGIN, 405),
        size=30,
        color=colors.teal_soft,
        width=WIDTH - MARGIN * 2,
        lines=1,
    )

    left = (MARGIN, 520, 510, 1155)
    right = (570, 520, WIDTH - MARGIN, 1155)
    draw.rounded_rectangle(left, radius=32, fill=colors.navy_soft)
    draw.rounded_rectangle(right, radius=32, fill=colors.white)
    draw.text((293, 580), "模糊指令", font=_font(31, bold=True), fill=colors.white, anchor="mm")
    draw.text((787, 580), "结构化指令", font=_font(31, bold=True), fill=colors.navy, anchor="mm")

    for index, label in enumerate(("机器人", "发光大脑", "代码雨", "元素堆满")):
        y = 665 + index * 105
        draw.rounded_rectangle((125, y, 455, y + 70), radius=16, fill="#294B73")
        draw.text((290, y + 35), label, font=_font(25), fill=colors.teal_soft, anchor="mm")

    draw.rounded_rectangle((625, 665, 950, 790), radius=18, fill=colors.teal_soft)
    draw.text((787, 727), "顶部留标题区", font=_font(25, bold=True), fill=colors.navy, anchor="mm")
    draw.rounded_rectangle((625, 835, 755, 1030), radius=18, fill=colors.surface)
    draw.ellipse((665, 885, 715, 935), fill=colors.teal)
    draw.line((690, 940, 690, 985), fill=colors.teal, width=13)
    draw.rounded_rectangle((820, 835, 950, 1030), radius=18, fill=colors.teal_soft)
    for y in (885, 930, 975):
        draw.line((847, y, 922, y), fill=colors.teal, width=9)
    draw.line((765, 930, 810, 930), fill=colors.teal, width=8)
    draw.polygon(((810, 930), (790, 916), (790, 944)), fill=colors.teal)

    draw.rounded_rectangle((MARGIN, 1210, WIDTH - MARGIN, 1280), radius=20, fill="#152D4B")
    draw.text(
        (WIDTH // 2, 1245),
        "概念示意｜不是具体工具横评",
        font=_font(24),
        fill=colors.teal_soft,
        anchor="mm",
    )
    draw.text((MARGIN, 1375), BRAND, font=_font(22, bold=True), fill=colors.teal)
    image.save(output, format="PNG", optimize=True)


def _render_failure(output: Path) -> None:
    image, draw, colors = _canvas()
    y = _header(
        draw,
        colors,
        number="01",
        title="为什么总生成“素材图”？",
        subtitle="“科技感、高级感”几乎没有提供可执行信息",
    )
    _card(draw, (MARGIN, y + 55, WIDTH - MARGIN, y + 300), colors, fill=colors.warning_background)
    draw.text(
        (WIDTH // 2, y + 115),
        "帮我生成一张",
        font=_font(34),
        fill=colors.text,
        anchor="ma",
    )
    draw.text(
        (WIDTH // 2, y + 180),
        "有科技感、高级感的 AI 封面",
        font=_font(38, bold=True),
        fill=colors.navy,
        anchor="ma",
    )
    draw.text(
        (WIDTH // 2, y + 255),
        "× 场景不清楚　× 主体没限制　× 构图没说明",
        font=_font(25),
        fill=colors.muted,
        anchor="ma",
    )

    labels = (("机器人", "泛科技"), ("代码雨", "画面乱"), ("霓虹光", "难放标题"))
    start_y = y + 365
    for index, (label, result) in enumerate(labels):
        x1 = MARGIN + index * 310
        x2 = x1 + 275
        _card(draw, (x1, start_y, x2, start_y + 305), colors)
        draw.ellipse((x1 + 82, start_y + 48, x1 + 193, start_y + 159), fill=colors.teal_soft)
        draw.text((x1 + 138, start_y + 104), "×", font=_font(48, bold=True), fill=colors.teal, anchor="mm")
        draw.text((x1 + 138, start_y + 205), label, font=_font(29, bold=True), fill=colors.navy, anchor="mm")
        draw.text((x1 + 138, start_y + 252), result, font=_font(24), fill=colors.muted, anchor="mm")

    _text(
        draw,
        "先把“高级感”翻译成具体的场景、主体、构图、颜色和禁用元素。",
        xy=(MARGIN, start_y + 380),
        size=32,
        color=colors.navy,
        width=WIDTH - MARGIN * 2,
        lines=2,
        bold=True,
    )
    _footer(draw, colors, 2)
    image.save(output, format="PNG", optimize=True)


def _render_scene_subject(output: Path) -> None:
    image, draw, colors = _canvas()
    y = _header(
        draw,
        colors,
        number="02",
        title="先写场景，再限制主体",
        subtitle="一张封面只传递一个动作，比堆满元素更容易看懂",
    )
    sections = (
        (
            "使用场景",
            "面向普通职场人的文章封面，主题是“AI 帮人整理会议待办”。",
        ),
        (
            "画面主体",
            "只保留一个人物、一份杂乱会议记录，以及一张整理后的待办清单。",
        ),
    )
    for index, (heading, body) in enumerate(sections):
        top = y + 55 + index * 365
        _card(draw, (MARGIN, top, WIDTH - MARGIN, top + 315), colors)
        draw.rounded_rectangle((MARGIN + 35, top + 35, MARGIN + 215, top + 83), radius=24, fill=colors.teal)
        draw.text(
            (MARGIN + 125, top + 59),
            heading,
            font=_font(24, bold=True),
            fill=colors.white,
            anchor="mm",
        )
        _text(
            draw,
            body,
            xy=(MARGIN + 40, top + 120),
            size=34,
            color=colors.navy,
            width=WIDTH - MARGIN * 2 - 80,
            lines=3,
            bold=True,
            spacing=18,
        )
    _card(draw, (MARGIN, y + 815, WIDTH - MARGIN, y + 1010), colors, fill=colors.teal_soft)
    draw.text(
        (WIDTH // 2, y + 875),
        "删掉这些泛化元素",
        font=_font(28, bold=True),
        fill=colors.navy,
        anchor="mm",
    )
    draw.text(
        (WIDTH // 2, y + 945),
        "机器人脸　芯片　代码雨　发光大脑",
        font=_font(29),
        fill=colors.text,
        anchor="mm",
    )
    _footer(draw, colors, 3)
    image.save(output, format="PNG", optimize=True)


def _render_layout(output: Path) -> None:
    image, draw, colors = _canvas()
    y = _header(
        draw,
        colors,
        number="03",
        title="直接告诉 AI 怎么摆",
        subtitle="主体位置和标题安全区，应该写进提示词",
    )
    top = y + 55
    _card(draw, (MARGIN, top, WIDTH - MARGIN, top + 650), colors)
    frame = (MARGIN + 55, top + 55, WIDTH - MARGIN - 55, top + 565)
    draw.rounded_rectangle(frame, radius=22, fill=colors.surface, outline=colors.border, width=3)
    draw.rounded_rectangle(
        (frame[0] + 30, frame[1] + 25, frame[2] - 30, frame[1] + 145),
        radius=14,
        fill=colors.teal_soft,
        outline=colors.teal,
        width=3,
    )
    draw.text(
        (WIDTH // 2, frame[1] + 85),
        "顶部约 25%：标题安全区",
        font=_font(28, bold=True),
        fill=colors.navy,
        anchor="mm",
    )
    draw.rounded_rectangle((frame[0] + 30, frame[1] + 190, WIDTH // 2 - 35, frame[3] - 30), radius=18, fill=colors.white)
    draw.rounded_rectangle((WIDTH // 2 + 35, frame[1] + 190, frame[2] - 30, frame[3] - 30), radius=18, fill=colors.teal_soft)
    draw.text((310, frame[1] + 285), "杂乱记录", font=_font(27, bold=True), fill=colors.navy, anchor="mm")
    draw.text((770, frame[1] + 285), "清晰待办", font=_font(27, bold=True), fill=colors.navy, anchor="mm")
    draw.line((480, frame[1] + 285, 600, frame[1] + 285), fill=colors.teal, width=10)
    draw.polygon(((600, frame[1] + 285), (570, frame[1] + 265), (570, frame[1] + 305)), fill=colors.teal)

    prompt = "左侧是杂乱记录，右侧是清晰待办，中间用简洁箭头连接；顶部留出标题安全区。"
    _card(draw, (MARGIN, top + 705, WIDTH - MARGIN, top + 940), colors, fill=colors.navy)
    _text(
        draw,
        prompt,
        xy=(MARGIN + 38, top + 755),
        size=30,
        color=colors.white,
        width=WIDTH - MARGIN * 2 - 76,
        lines=3,
        bold=True,
        spacing=16,
    )
    _footer(draw, colors, 4)
    image.save(output, format="PNG", optimize=True)


def _render_style(output: Path) -> None:
    image, draw, colors = _canvas()
    y = _header(
        draw,
        colors,
        number="04",
        title="颜色不超过 3 种",
        subtitle="再明确“不要什么”，减少常见废片",
    )
    top = y + 55
    _card(draw, (MARGIN, top, WIDTH - MARGIN, top + 330), colors)
    draw.text((MARGIN + 40, top + 45), "推荐配色", font=_font(29, bold=True), fill=colors.navy)
    swatches = ((colors.navy, "深蓝"), (colors.white, "白色"), (colors.teal, "青绿"))
    for index, (color, label) in enumerate(swatches):
        x = MARGIN + 45 + index * 295
        draw.rounded_rectangle((x, top + 110, x + 230, top + 230), radius=22, fill=color, outline=colors.border, width=2)
        draw.text((x + 115, top + 270), label, font=_font(24, bold=True), fill=colors.text, anchor="mm")

    _card(draw, (MARGIN, top + 380, WIDTH - MARGIN, top + 830), colors, fill=colors.white)
    draw.text((MARGIN + 40, top + 430), "明确禁用", font=_font(29, bold=True), fill=colors.navy)
    forbidden = ("不生成文字", "不出现品牌标志", "不用机器人脸", "不用机械手", "不用发光大脑", "不用代码雨")
    for index, item in enumerate(forbidden):
        col = index % 2
        row = index // 2
        x = MARGIN + 40 + col * 455
        item_y = top + 510 + row * 92
        draw.ellipse((x, item_y, x + 38, item_y + 38), fill=colors.teal_soft)
        draw.text((x + 19, item_y + 19), "×", font=_font(25, bold=True), fill=colors.teal, anchor="mm")
        draw.text((x + 57, item_y + 19), item, font=_font(25), fill=colors.text, anchor="lm")
    _text(
        draw,
        "负面约束不能保证一次成功，但能减少方向完全跑偏。",
        xy=(MARGIN, top + 900),
        size=31,
        color=colors.navy,
        width=WIDTH - MARGIN * 2,
        lines=2,
        bold=True,
    )
    _footer(draw, colors, 5)
    image.save(output, format="PNG", optimize=True)


def _render_prompt(output: Path) -> None:
    image, draw, colors = _canvas()
    y = _header(
        draw,
        colors,
        number="05",
        title="复制后，替换主题即可",
        subtitle="一条完整提示词，至少包含这 5 部分",
    )
    top = y + 45
    items = (
        ("场景", "面向普通职场人的文章封面"),
        ("主题", "AI 帮人整理会议待办"),
        ("主体", "人物＋杂乱记录＋待办清单"),
        ("构图", "左右对比，顶部留 25%"),
        ("风格", "专业极简，深蓝＋白＋青绿"),
    )
    for index, (label, value) in enumerate(items):
        item_y = top + index * 145
        _card(draw, (MARGIN, item_y, WIDTH - MARGIN, item_y + 115), colors)
        draw.rounded_rectangle((MARGIN + 24, item_y + 25, MARGIN + 150, item_y + 90), radius=20, fill=colors.teal)
        draw.text(
            (MARGIN + 87, item_y + 58),
            label,
            font=_font(25, bold=True),
            fill=colors.white,
            anchor="mm",
        )
        draw.text(
            (MARGIN + 185, item_y + 58),
            value,
            font=_font(27, bold=True),
            fill=colors.navy,
            anchor="lm",
        )
    _card(draw, (MARGIN, top + 750, WIDTH - MARGIN, top + 1010), colors, fill=colors.navy)
    _text(
        draw,
        "禁用：文字、品牌标志、机器人脸、机械手、发光大脑、代码雨和复杂装饰。",
        xy=(MARGIN + 40, top + 810),
        size=29,
        color=colors.white,
        width=WIDTH - MARGIN * 2 - 80,
        lines=3,
        bold=True,
        spacing=17,
    )
    _footer(draw, colors, 6)
    image.save(output, format="PNG", optimize=True)


def _render_checklist(output: Path) -> None:
    image, draw, colors = _canvas()
    y = _header(
        draw,
        colors,
        number="06",
        title="生成后，先别急着发",
        subtitle="这 3 项仍然需要人工确认",
    )
    checks = (
        ("手机缩略图", "缩小后，主体还能不能一眼看懂？"),
        ("标题安全区", "标题放上去，会不会挡住关键画面？"),
        ("明显错误", "手指、纸张、图标和人物表情是否异常？"),
    )
    for index, (heading, body) in enumerate(checks, start=1):
        top = y + 55 + (index - 1) * 265
        _card(draw, (MARGIN, top, WIDTH - MARGIN, top + 220), colors)
        draw.ellipse((MARGIN + 38, top + 54, MARGIN + 126, top + 142), fill=colors.teal)
        draw.text(
            (MARGIN + 82, top + 98),
            str(index),
            font=_font(34, bold=True),
            fill=colors.white,
            anchor="mm",
        )
        draw.text((MARGIN + 165, top + 57), heading, font=_font(31, bold=True), fill=colors.navy)
        _text(
            draw,
            body,
            xy=(MARGIN + 165, top + 112),
            size=26,
            color=colors.text,
            width=WIDTH - MARGIN * 2 - 205,
            lines=2,
        )
    _card(draw, (MARGIN, y + 865, WIDTH - MARGIN, y + 1065), colors, fill=colors.teal_soft)
    _text(
        draw,
        "连续改三次还不对？先减少主体，再重写构图，不要继续堆形容词。",
        xy=(MARGIN + 38, y + 915),
        size=30,
        color=colors.navy,
        width=WIDTH - MARGIN * 2 - 76,
        lines=3,
        bold=True,
        spacing=16,
    )
    _footer(draw, colors, 7)
    image.save(output, format="PNG", optimize=True)


def render_cards(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    renderers = (
        ("01-cover.png", _render_cover),
        ("02-common-failure.png", _render_failure),
        ("03-scene-and-subject.png", _render_scene_subject),
        ("04-layout-and-safe-zone.png", _render_layout),
        ("05-style-and-negative.png", _render_style),
        ("06-copyable-prompt.png", _render_prompt),
        ("07-publish-checklist.png", _render_checklist),
    )
    outputs: list[Path] = []
    for filename, renderer in renderers:
        output = output_dir / filename
        renderer(output)
        outputs.append(output)
    return outputs


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[3]
    destination = project_root / "assets" / "xiaohongshu-ai-cover-workflow-20260729"
    for path in render_cards(destination):
        print(path)
