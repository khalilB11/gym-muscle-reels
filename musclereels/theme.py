"""Colors and fonts."""
from __future__ import annotations

import os
from dataclasses import dataclass, fields
from functools import lru_cache

from PIL import ImageFont

RGBA = tuple[int, int, int, int]


def hex_to_rgba(value: str | tuple) -> RGBA:
    if isinstance(value, (tuple, list)):
        v = tuple(int(c) for c in value)
        return v if len(v) == 4 else (*v, 255)  # type: ignore[return-value]
    h = value.lstrip("#")
    if len(h) == 6:
        h += "ff"
    if len(h) != 8:
        raise ValueError(f"Bad color '{value}', use #RRGGBB or #RRGGBBAA")
    return tuple(int(h[i:i + 2], 16) for i in range(0, 8, 2))  # type: ignore[return-value]


@dataclass
class Theme:
    primary: RGBA = (255, 59, 48, 255)       # main target muscles
    secondary: RGBA = (255, 159, 10, 255)    # assisting muscles
    inactive: RGBA = (58, 64, 76, 255)
    filler: RGBA = (43, 48, 58, 255)         # head, hands, joints
    gap: RGBA = (16, 18, 22, 255)            # lines between muscles
    card: RGBA = (12, 14, 18, 200)           # card background
    text: RGBA = (255, 255, 255, 255)
    muted: RGBA = (160, 168, 180, 255)
    font: str | None = None                  # path to a bold .ttf/.otf
    font_regular: str | None = None

    def to_dict(self, only_changed: bool = False) -> dict:
        default = Theme()
        out = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if only_changed and v == getattr(default, f.name):
                continue
            out[f.name] = v if f.name.startswith("font") else "#" + "".join(f"{c:02X}" for c in v)
        return out

    @classmethod
    def from_dict(cls, data: dict | None) -> "Theme":
        theme = cls()
        for f in fields(cls):
            if data and f.name in data:
                value = data[f.name]
                setattr(theme, f.name, value if f.name.startswith("font") else hex_to_rgba(value))
        return theme


_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
]
_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
]


@lru_cache(maxsize=64)
def load_font(size: int, bold: bool = True, path: str | None = None) -> ImageFont.FreeTypeFont:
    candidates = [path, os.environ.get("MUSCLEREELS_FONT" if bold else "MUSCLEREELS_FONT_REGULAR")]
    candidates += _BOLD if bold else _REGULAR
    for c in candidates:
        if c and os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default(size=size)
