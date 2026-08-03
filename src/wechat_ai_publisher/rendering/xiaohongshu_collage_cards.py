from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from wechat_ai_publisher.rendering.template_images import _font, _wrap

W, H = 1080, 1440
INK = "#24303A"
MUTED = "#667078"
CREAM = "#F3EBDD"
PAPER = "#FFFCF5"
TEAL = "#157F78"
CORAL = "#E86F51"
YELLOW = "#F4D35E"
BLUE = "#DCEAF0"
BRAND = "智效进化论"


def _desk(seed: int) -> Image.Image:
    rng = random.Random(seed)
    image = Image.new("RGB", (W, H), CREAM)
    pixels = image.load()
    for _ in range(26000):
        x, y = rng.randrange(W), rng.randrange(H)
        base = rng.choice((-8, -5, 4, 7))
        r, g, b = pixels[x, y]
        pixels[x, y] = (
            max(0, min(255, r + base)),
            max(0, min(255, g + base)),
            max(0, min(255, b + base)),
        )
    draw = ImageDraw.Draw(image)
    for y in range(90, H, 96):
        draw.line((0, y, W, y + rng.randint(-3, 3)), fill="#E9DFCF", width=1)
    return image


def _write(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    *,
    size: int,
    color: str = INK,
    width: int,
    lines: int = 5,
    bold: bool = False,
    gap: int = 12,
) -> int:
    font = _font(size, bold=bold)
    wrapped = _wrap(draw, text, font, width, lines)
    y = xy[1]
    for line in wrapped:
        draw.text((xy[0], y), line, font=font, fill=color)
        y += size + gap
    return y


def _paper(
    size: tuple[int, int],
    *,
    color: str = PAPER,
    radius: int = 22,
    grid: bool = False,
) -> Image.Image:
    width, height = size
    layer = Image.new("RGBA", (width + 50, height + 50), (0, 0, 0, 0))
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((22, 24, width + 22, height + 24), radius=radius, fill=(65, 51, 35, 55))
    shadow = shadow.filter(ImageFilter.GaussianBlur(13))
    layer.alpha_composite(shadow)
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((10, 10, width + 10, height + 10), radius=radius, fill=color)
    if grid:
        for x in range(35, width, 42):
            draw.line((x, 10, x, height + 10), fill="#D7E5E8", width=1)
        for y in range(35, height, 42):
            draw.line((10, y, width + 10, y), fill="#D7E5E8", width=1)
    return layer


def _paste(image: Image.Image, layer: Image.Image, xy: tuple[int, int], angle: float = 0) -> None:
    rotated = layer.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    image.alpha_composite(rotated, xy)


def _tape(image: Image.Image, xy: tuple[int, int], *, angle: float = 0, width: int = 150) -> None:
    tape = Image.new("RGBA", (width, 45), (236, 205, 129, 190))
    td = ImageDraw.Draw(tape)
    for x in range(8, width, 18):
        td.line((x, 0, x + 5, 45), fill=(255, 240, 190, 90), width=2)
    tape = tape.rotate(angle, expand=True)
    image.alpha_composite(tape, xy)


def _footer(draw: ImageDraw.ImageDraw, text: str = BRAND) -> None:
    draw.text((60, 1382), text, font=_font(20, bold=True), fill="#7D776D")


def _marker(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color: str = YELLOW) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1, y1, x2, y2), radius=12, fill=color)


def _cover(output: Path) -> None:
    image = _desk(1).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.text((64, 60), "AI 图像轻教程", font=_font(24, bold=True), fill=TEAL)
    draw.text((62, 135), "AI 做封面", font=_font(82, bold=True), fill=INK)
    _marker(draw, (56, 245, 660, 330), "#F7D861")
    draw.text((72, 247), "别只写“高级感”", font=_font(55, bold=True), fill=INK)
    draw.text((66, 365), "把一句空话，拆成 5 个可修改的部分", font=_font(28), fill=MUTED)

    left = _paper((425, 570), color="#F8F3E8")
    ld = ImageDraw.Draw(left)
    ld.text((42, 45), "模糊指令", font=_font(29, bold=True), fill=CORAL)
    ld.text((42, 110), "“科技感、高级感”", font=_font(32, bold=True), fill=INK)
    ld.line((38, 168, 365, 168), fill=CORAL, width=7)
    for index, item in enumerate(("机器人", "发光大脑", "代码雨", "元素堆满")):
        y = 235 + index * 68
        ld.text((62, y), f"×  {item}", font=_font(26), fill=MUTED)
    ld.text((42, 510), "信息很多，主题不清楚", font=_font(23), fill=CORAL)
    _paste(image, left, (70, 500), angle=-3)
    _tape(image, (205, 475), angle=-5)

    right = _paper((440, 610), color=PAPER)
    rd = ImageDraw.Draw(right)
    rd.text((42, 44), "结构化指令", font=_font(29, bold=True), fill=TEAL)
    labels = (
        ("场景", "职场文章封面"),
        ("主体", "人物＋记录＋待办"),
        ("构图", "左右对比"),
        ("颜色", "深蓝＋白＋青绿"),
        ("禁用", "文字、Logo、代码雨"),
    )
    for index, (label, value) in enumerate(labels):
        y = 120 + index * 88
        rd.rounded_rectangle((40, y, 126, y + 48), radius=12, fill="#D8EEE9")
        rd.text((83, y + 24), label, font=_font(20, bold=True), fill=TEAL, anchor="mm")
        rd.text((150, y + 24), value, font=_font(23), fill=INK, anchor="lm")
    rd.text((42, 555), "每一项都能单独修改", font=_font(23, bold=True), fill=TEAL)
    _paste(image, right, (555, 470), angle=2)
    _tape(image, (725, 470), angle=4)

    draw.text((66, 1278), "概念拆解，不是具体工具横评", font=_font(23), fill=MUTED)
    _footer(draw)
    image.convert("RGB").save(output, format="PNG", optimize=True)


def _bad_prompt(output: Path) -> None:
    image = _desk(2).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.text((62, 65), "01", font=_font(23, bold=True), fill=CORAL)
    draw.text((62, 118), "这句提示词，问题在哪？", font=_font(57, bold=True), fill=INK)

    note = _paper((875, 310), color="#FFF9DD")
    nd = ImageDraw.Draw(note)
    nd.text((50, 54), "帮我生成一张", font=_font(30), fill=MUTED)
    nd.text((50, 122), "有科技感、高级感的 AI 封面", font=_font(39, bold=True), fill=INK)
    nd.line((45, 181, 780, 181), fill=CORAL, width=8)
    nd.text((50, 220), "听起来明确，其实没有可执行细节", font=_font(25), fill=CORAL)
    _paste(image, note, (88, 265), angle=-1.5)
    _tape(image, (435, 247), angle=1)

    labels = (
        ("场景？", "给谁看，放在哪里？"),
        ("主体？", "画面里到底出现什么？"),
        ("构图？", "标题和主体怎么摆？"),
    )
    for index, (title, body) in enumerate(labels):
        x = 70 + index * 330
        paper = _paper((280, 330), color=("#E7F1F0" if index != 1 else "#F4E4DC"))
        pd = ImageDraw.Draw(paper)
        pd.text((34, 40), title, font=_font(34, bold=True), fill=TEAL if index != 1 else CORAL)
        _write(pd, body, (34, 115), size=27, color=INK, width=215, lines=3, bold=True)
        pd.text((34, 267), "没有答案", font=_font(22), fill=MUTED)
        _paste(image, paper, (x, 680 + (index % 2) * 20), angle=(-3 + index * 3))

    _marker(draw, (70, 1158, 960, 1235), "#F6D96C")
    _write(
        draw,
        "先把“高级感”翻译成：场景、主体、构图、颜色、禁用元素。",
        (84, 1168),
        size=29,
        color=INK,
        width=850,
        lines=2,
        bold=True,
    )
    _footer(draw)
    image.convert("RGB").save(output, format="PNG", optimize=True)


def _scene_subject(output: Path) -> None:
    image = _desk(3).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.text((62, 62), "02", font=_font(23, bold=True), fill=TEAL)
    draw.text((62, 118), "先写场景，再限制主体", font=_font(56, bold=True), fill=INK)
    draw.text((64, 198), "一张封面，只传递一个动作", font=_font(29), fill=MUTED)

    scene = _paper((760, 350), color="#DDEDEA")
    sd = ImageDraw.Draw(scene)
    sd.text((45, 40), "场景", font=_font(25, bold=True), fill=TEAL)
    _write(
        sd,
        "面向普通职场人的文章封面，主题是“AI 帮人整理会议待办”。",
        (45, 100),
        size=35,
        color=INK,
        width=670,
        lines=4,
        bold=True,
        gap=16,
    )
    _paste(image, scene, (115, 300), angle=-2)
    _tape(image, (400, 276), angle=-2)

    subject = _paper((760, 350), color="#FFF8DB")
    pd = ImageDraw.Draw(subject)
    pd.text((45, 40), "主体", font=_font(25, bold=True), fill=CORAL)
    _write(
        pd,
        "只保留一个人物、一份杂乱会议记录，以及一张整理后的待办清单。",
        (45, 100),
        size=35,
        color=INK,
        width=670,
        lines=4,
        bold=True,
        gap=16,
    )
    _paste(image, subject, (200, 720), angle=2)
    _tape(image, (500, 708), angle=3)

    draw.arc((78, 1000, 350, 1260), 210, 40, fill=CORAL, width=8)
    draw.polygon(((326, 1180), (292, 1162), (299, 1200)), fill=CORAL)
    draw.text((75, 1210), "删掉：机器人、芯片、代码雨", font=_font(27, bold=True), fill=CORAL)
    _footer(draw)
    image.convert("RGB").save(output, format="PNG", optimize=True)


def _layout(output: Path) -> None:
    image = _desk(4).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.text((62, 62), "03", font=_font(23, bold=True), fill=TEAL)
    draw.text((62, 118), "别让 AI 自己猜构图", font=_font(56, bold=True), fill=INK)
    draw.text((64, 198), "直接画给它看，也写给它看", font=_font(29), fill=MUTED)

    board = _paper((900, 760), color="#F8FCFC", grid=True)
    bd = ImageDraw.Draw(board)
    bd.rounded_rectangle((60, 55, 840, 205), radius=18, outline=TEAL, width=5)
    bd.text((450, 130), "顶部约 25%：标题安全区", font=_font(31, bold=True), fill=TEAL, anchor="mm")
    bd.rounded_rectangle((60, 265, 390, 640), radius=20, fill="#FFF7E1", outline="#D9CDB0", width=3)
    bd.rounded_rectangle((510, 265, 840, 640), radius=20, fill="#DDEDEA", outline="#B7D8D2", width=3)
    bd.text((225, 450), "杂乱记录", font=_font(33, bold=True), fill=INK, anchor="mm")
    bd.text((675, 450), "清晰待办", font=_font(33, bold=True), fill=INK, anchor="mm")
    bd.line((400, 450, 500, 450), fill=CORAL, width=10)
    bd.polygon(((500, 450), (470, 430), (470, 470)), fill=CORAL)
    bd.text((60, 690), "草图不用漂亮，只要位置关系明确", font=_font(25), fill=MUTED)
    _paste(image, board, (70, 300), angle=-1)
    _tape(image, (445, 278), angle=1)

    quote = _paper((850, 190), color="#263843")
    qd = ImageDraw.Draw(quote)
    _write(
        qd,
        "左侧是杂乱记录，右侧是清晰待办；顶部留出标题安全区。",
        (42, 42),
        size=29,
        color="#FFFFFF",
        width=760,
        lines=3,
        bold=True,
    )
    _paste(image, quote, (125, 1115), angle=1)
    _footer(draw)
    image.convert("RGB").save(output, format="PNG", optimize=True)


def _style(output: Path) -> None:
    image = _desk(5).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.text((62, 62), "04", font=_font(23, bold=True), fill=CORAL)
    draw.text((62, 118), "颜色少一点，废片少一点", font=_font(53, bold=True), fill=INK)
    draw.text((64, 198), "先定 3 种颜色，再写清楚“不要什么”", font=_font(29), fill=MUTED)

    palette = _paper((900, 330), color=PAPER)
    pd = ImageDraw.Draw(palette)
    pd.text((45, 38), "这组内容的配色", font=_font(27, bold=True), fill=INK)
    colors = (("#183248", "深蓝"), ("#FFFCF5", "米白"), ("#1A8B82", "青绿"))
    for index, (color, label) in enumerate(colors):
        x = 55 + index * 280
        pd.ellipse((x, 115, x + 150, 265), fill=color, outline="#D8D0C2", width=2)
        pd.text((x + 190, 190), label, font=_font(25, bold=True), fill=INK, anchor="mm")
    _paste(image, palette, (80, 300), angle=-2)
    _tape(image, (400, 280), angle=-3)

    forbidden = _paper((790, 510), color="#F6E4DE")
    fd = ImageDraw.Draw(forbidden)
    fd.text((45, 42), "明确禁用", font=_font(32, bold=True), fill=CORAL)
    items = ("图片内文字", "品牌标志", "机器人脸", "机械手", "发光大脑", "代码雨")
    for index, item in enumerate(items):
        col, row = index % 2, index // 2
        x, y = 55 + col * 360, 125 + row * 95
        fd.ellipse((x, y, x + 42, y + 42), outline=CORAL, width=5)
        fd.line((x + 8, y + 8, x + 34, y + 34), fill=CORAL, width=5)
        fd.line((x + 34, y + 8, x + 8, y + 34), fill=CORAL, width=5)
        fd.text((x + 62, y + 21), item, font=_font(26), fill=INK, anchor="lm")
    fd.text((45, 430), "不是保证成功，而是减少方向跑偏", font=_font(25, bold=True), fill=MUTED)
    _paste(image, forbidden, (185, 770), angle=2)
    _tape(image, (515, 752), angle=3)
    _footer(draw)
    image.convert("RGB").save(output, format="PNG", optimize=True)


def _prompt(output: Path) -> None:
    image = _desk(6).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.text((62, 62), "05", font=_font(23, bold=True), fill=TEAL)
    draw.text((62, 118), "把提示词写成“可替换模板”", font=_font(51, bold=True), fill=INK)
    draw.text((64, 198), "下次换主题，不用从头再写", font=_font(29), fill=MUTED)

    sheet = _paper((900, 940), color=PAPER)
    sd = ImageDraw.Draw(sheet)
    sd.text((55, 45), "PROMPT / 封面提示词", font=_font(25, bold=True), fill=TEAL)
    fields = (
        ("场景", "面向普通职场人的文章封面"),
        ("主题", "AI 帮人整理会议待办"),
        ("主体", "人物＋杂乱记录＋待办清单"),
        ("构图", "左右对比，顶部留 25%"),
        ("风格", "专业极简，深蓝＋白＋青绿"),
    )
    marker_colors = ("#F7DB6D", "#D7ECE8", "#F3D7CE", "#DDEAF1", "#F7DB6D")
    for index, ((label, value), marker_color) in enumerate(zip(fields, marker_colors, strict=True)):
        y = 130 + index * 130
        sd.rounded_rectangle((50, y, 160, y + 52), radius=12, fill=marker_color)
        sd.text((105, y + 26), label, font=_font(23, bold=True), fill=INK, anchor="mm")
        sd.text((195, y + 26), value, font=_font(27, bold=True), fill=INK, anchor="lm")
        sd.line((195, y + 67, 825, y + 67), fill="#DED7CB", width=2)
    sd.rounded_rectangle((50, 805, 850, 895), radius=18, fill="#263843")
    sd.text(
        (75, 850),
        "禁用：文字、Logo、机器人脸、机械手、发光大脑、代码雨",
        font=_font(23, bold=True),
        fill="#FFFFFF",
        anchor="lm",
    )
    _paste(image, sheet, (85, 300), angle=-1)
    _tape(image, (460, 280), angle=-1)
    draw.text((68, 1300), "复制时只替换高亮字段", font=_font(29, bold=True), fill=CORAL)
    draw.line((64, 1342, 440, 1342), fill=CORAL, width=6)
    _footer(draw, "")
    image.convert("RGB").save(output, format="PNG", optimize=True)


def _checklist(output: Path) -> None:
    image = _desk(7).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.text((62, 62), "06", font=_font(23, bold=True), fill=CORAL)
    draw.text((62, 118), "生成后，先别急着发", font=_font(58, bold=True), fill=INK)
    draw.text((64, 200), "最后 3 分钟，检查这三件事", font=_font(29), fill=MUTED)

    clipboard = _paper((810, 875), color="#FAF7EE")
    cd = ImageDraw.Draw(clipboard)
    cd.rounded_rectangle((280, 18, 550, 85), radius=18, fill="#B9A98C")
    cd.text((415, 52), "发布前检查", font=_font(26, bold=True), fill="#FFFFFF", anchor="mm")
    checks = (
        ("01", "手机缩略图", "缩小后，主体还能一眼看懂吗？"),
        ("02", "标题安全区", "标题放上去，会挡住关键画面吗？"),
        ("03", "明显错误", "手指、纸张、图标和表情正常吗？"),
    )
    for index, (number, title, body) in enumerate(checks):
        y = 145 + index * 220
        cd.ellipse((60, y, 125, y + 65), fill=TEAL if index != 1 else CORAL)
        cd.text((92, y + 33), number, font=_font(19, bold=True), fill="#FFFFFF", anchor="mm")
        cd.text((160, y + 2), title, font=_font(32, bold=True), fill=INK)
        cd.text((160, y + 60), body, font=_font(25), fill=MUTED)
        cd.line((60, y + 145, 745, y + 145), fill="#DDD4C4", width=2)
    cd.text((60, 795), "□  我已经用手机预览过整组图片", font=_font(27, bold=True), fill=INK)
    _paste(image, clipboard, (135, 310), angle=1.5)
    _tape(image, (485, 288), angle=2)

    sticky = _paper((770, 150), color="#F7DB6D", radius=8)
    st = ImageDraw.Draw(sticky)
    _write(
        st,
        "连续改三次还不对？先减少主体，再重写构图。",
        (35, 30),
        size=28,
        color=INK,
        width=690,
        lines=2,
        bold=True,
    )
    _paste(image, sticky, (190, 1218), angle=-2)
    _footer(draw)
    image.convert("RGB").save(output, format="PNG", optimize=True)


def render_cards(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    renderers = (
        ("01-cover.png", _cover),
        ("02-common-failure.png", _bad_prompt),
        ("03-scene-and-subject.png", _scene_subject),
        ("04-layout-and-safe-zone.png", _layout),
        ("05-style-and-negative.png", _style),
        ("06-copyable-prompt.png", _prompt),
        ("07-publish-checklist.png", _checklist),
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
