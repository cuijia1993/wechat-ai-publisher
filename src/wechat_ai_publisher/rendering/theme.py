from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ThemeColors(BaseModel):
    navy: str = "#0B1F3A"
    navy_soft: str = "#1E3A5F"
    teal: str = "#0F9F91"
    teal_soft: str = "#DFF5F2"
    text: str = "#2B3340"
    muted: str = "#718096"
    surface: str = "#F4F8F8"
    border: str = "#D7E4E5"
    white: str = "#FFFFFF"
    code_background: str = "#101C2C"
    code_text: str = "#E6F1F0"
    warning_background: str = "#FFF8E8"
    warning_border: str = "#E5B94E"


class ThemeTypography(BaseModel):
    body_size: int = 16
    body_line_height: float = 1.8
    h1_size: int = 24
    h2_size: int = 20
    h3_size: int = 17
    note_size: int = 13
    code_size: int = 13


class ThemeSpacing(BaseModel):
    page_padding: int = 20
    paragraph_margin: int = 14
    section_margin: int = 30
    block_margin: int = 20
    radius: int = 8


class VisualTheme(BaseModel):
    id: str = "professional-minimal"
    name: str = "智效进化社专业极简"
    colors: ThemeColors = Field(default_factory=ThemeColors)
    typography: ThemeTypography = Field(default_factory=ThemeTypography)
    spacing: ThemeSpacing = Field(default_factory=ThemeSpacing)


def load_theme(path: str | Path) -> VisualTheme:
    with Path(path).open(encoding="utf-8") as handle:
        return VisualTheme.model_validate(yaml.safe_load(handle) or {})

