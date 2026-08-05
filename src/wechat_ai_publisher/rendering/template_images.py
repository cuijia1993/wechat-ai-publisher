from __future__ import annotations

import re
import shutil
import tempfile
import urllib.request
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from wechat_ai_publisher.rendering.theme import VisualTheme

_BUNDLE_DIR = Path(__file__).resolve().parent / "fonts"
_USER_FONT_DIR = Path.home() / ".local" / "share" / "fonts" / "wechat-ai-publisher"

_FONT_DOWNLOAD_CANDIDATES = [
    # Debian 包内含 wqy-microhei，国内镜像可无 sudo 解压。
    (
        "https://mirrors.aliyun.com/debian/pool/main/f/fonts-wqy-microhei/"
        "fonts-wqy-microhei_0.2.0-beta-3.1_all.deb",
        "wqy-microhei.ttc",
    ),
    (
        "https://mirrors.tuna.tsinghua.edu.cn/debian/pool/main/f/fonts-wqy-microhei/"
        "fonts-wqy-microhei_0.2.0-beta-3.1_all.deb",
        "wqy-microhei.ttc",
    ),
]

_REGULAR_FONT_CANDIDATES = [
    _BUNDLE_DIR / "NotoSansSC-Regular.otf",
    _BUNDLE_DIR / "NotoSansCJKsc-Regular.otf",
    _BUNDLE_DIR / "wqy-microhei.ttc",
    _USER_FONT_DIR / "wqy-microhei.ttc",
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/System/Library/Fonts/STHeiti Light.ttc"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansSC-Regular.otf"),
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
]

_BOLD_FONT_CANDIDATES = [
    _BUNDLE_DIR / "NotoSansSC-Bold.otf",
    _BUNDLE_DIR / "NotoSansCJKsc-Bold.otf",
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansSC-Bold.otf"),
    # Linux 上缺独立 Bold 时，用常规中文字体也优于 Pillow 默认字体。
    *_REGULAR_FONT_CANDIDATES,
]


def _find_existing_font(*, bold: bool = False) -> Path | None:
    candidates = _BOLD_FONT_CANDIDATES if bold else _REGULAR_FONT_CANDIDATES
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _download_wqy_microhei(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for url, font_name in _FONT_DOWNLOAD_CANDIDATES:
        try:
            with tempfile.TemporaryDirectory(prefix="cjk-font-") as tmp:
                tmp_dir = Path(tmp)
                deb_path = tmp_dir / "font.deb"
                with urllib.request.urlopen(url, timeout=60) as response:
                    deb_path.write_bytes(response.read())
                extract_dir = tmp_dir / "extract"
                extract_dir.mkdir()
                # dpkg-deb 无需 root，适合无 sudo 的 self-hosted runner。
                import subprocess

                subprocess.run(
                    ["dpkg-deb", "-x", str(deb_path), str(extract_dir)],
                    check=True,
                    capture_output=True,
                )
                matches = list(extract_dir.rglob(font_name))
                if not matches:
                    raise FileNotFoundError(f"deb 中未找到 {font_name}")
                shutil.copy2(matches[0], destination)
                return destination
        except Exception as exc:  # noqa: BLE001 - 尝试下一个镜像
            last_error = exc
    raise FileNotFoundError(
        f"无法下载中文字体到 {destination}：{last_error}"
    )


def ensure_cjk_font(*, bold: bool = False) -> Path:
    """返回可用中文字体；若系统未安装则下载到用户可写目录。"""
    existing = _find_existing_font(bold=bold)
    if existing is not None:
        return existing
    downloaded = _download_wqy_microhei(_USER_FONT_DIR / "wqy-microhei.ttc")
    resolve_cjk_font_path.cache_clear()
    return downloaded


@lru_cache(maxsize=1)
def resolve_cjk_font_path(*, bold: bool = False) -> Path:
    existing = _find_existing_font(bold=bold)
    if existing is not None:
        return existing
    searched = ", ".join(str(path) for path in _REGULAR_FONT_CANDIDATES[:8])
    raise FileNotFoundError(
        "未找到可用中文字体，封面会乱码。请调用 ensure_cjk_font()，"
        f"或将字体放到 {_BUNDLE_DIR} / {_USER_FONT_DIR}。已尝试：{searched}"
    )


def _font(size: int, *, bold: bool = False):
    path = ensure_cjk_font(bold=bold)
    try:
        return ImageFont.truetype(str(path), size=size, index=0)
    except OSError:
        return ImageFont.truetype(str(path), size=size)


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
        brand: str = "智效进化论",
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
        brand: str = "智效进化论",
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
