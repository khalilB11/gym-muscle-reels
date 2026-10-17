"""Builds the on-screen graphics (title + body-map card) and blends them onto frames."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw

from .bodymap import display_name, render_figure
from .theme import Theme, load_font

CANVAS_W, CANVAS_H = 1080, 1920

# Areas Instagram covers with its own UI (header, caption, action buttons).
SAFE_TOP, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT = 250, 450, 60, 180

POSITIONS = ("left", "right", "center")


@dataclass
class Sprite:
    """A pre-rendered overlay piece. `delta` = lit - base, None for static pieces."""
    x: int
    y: int
    base: np.ndarray          # float32 BGRA, 0..255
    delta: np.ndarray | None

    @property
    def size(self) -> tuple[int, int]:
        h, w = self.base.shape[:2]
        return w, h


def _to_bgra(img: Image.Image) -> np.ndarray:
    a = np.asarray(img.convert("RGBA"), dtype=np.float32)
    return np.ascontiguousarray(a[..., [2, 1, 0, 3]])


def _text_size(draw: ImageDraw.ImageDraw, text: str, font, stroke: int = 0) -> tuple[int, int, int]:
    x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    return x1 - x0, y1 - y0, y0


def _title_sprite(title: str, subtitle: str | None, theme: Theme, max_w: int) -> Sprite:
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    text = title.upper()
    size = 80
    while True:
        font = load_font(size, True, theme.font)
        stroke = max(2, size // 14)
        tw, th, ty = _text_size(probe, text, font, stroke)
        if tw <= max_w or size <= 36:
            break
        size -= 4
    sub_font = load_font(max(26, size // 2), False, theme.font_regular)
    sw, sh, sy = _text_size(probe, subtitle, sub_font, 2) if subtitle else (0, 0, 0)

    bar_h, gap = 8, 14
    w = max(tw, sw) + 8
    h = th + gap + bar_h + ((gap + sh) if subtitle else 0) + 8
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text(((w - tw) // 2, -ty), text, font=font, fill=theme.text,
           stroke_width=stroke, stroke_fill=(0, 0, 0, 230))
    bar_w = min(160, w)
    by = th + gap
    d.rounded_rectangle(((w - bar_w) // 2, by, (w + bar_w) // 2, by + bar_h), radius=bar_h // 2, fill=theme.primary)
    if subtitle:
        d.text(((w - sw) // 2, by + bar_h + gap - sy), subtitle, font=sub_font, fill=theme.text,
               stroke_width=2, stroke_fill=(0, 0, 0, 230))
    return Sprite((CANVAS_W - w) // 2, SAFE_TOP, _to_bgra(img), None)


def _chips(primary: Sequence[str], secondary: Sequence[str], theme: Theme, max_w: int, scale: float):
    """Lay out legend chips; returns (draw_fn, height)."""
    font = load_font(round(26 * scale), True, theme.font)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    ch, pad_x, dot, gap = round(44 * scale), round(14 * scale), round(14 * scale), round(10 * scale)
    items = [(m, theme.primary) for m in primary] + [(m, theme.secondary) for m in secondary]
    placed, x, y = [], 0, 0
    for m, color in items:
        label = display_name(m)
        tw, th, ty = _text_size(probe, label, font)
        cw = pad_x + dot + gap + tw + pad_x
        if x and x + cw > max_w:
            x, y = 0, y + ch + gap
        placed.append((x, y, cw, label, color, th, ty))
        x += cw + gap
    height = (y + ch) if placed else 0

    def draw(d: ImageDraw.ImageDraw, ox: int, oy: int) -> None:
        for cx, cy, cw, label, color, th, ty in placed:
            x0, y0 = ox + cx, oy + cy
            d.rounded_rectangle((x0, y0, x0 + cw, y0 + ch), radius=ch // 2, fill=(255, 255, 255, 22))
            dy = y0 + (ch - dot) // 2
            d.ellipse((x0 + pad_x, dy, x0 + pad_x + dot, dy + dot), fill=color)
            d.text((x0 + pad_x + dot + gap, y0 + (ch - th) // 2 - ty), label, font=font, fill=theme.text)

    return draw, height


def _card_sprite(primary, secondary, theme: Theme, scale: float, x_pos: str, y: int) -> Sprite:
    fig_w = round(210 * scale)
    pad = round(22 * scale)
    label_h = round(34 * scale)
    figs = {
        (view, lit): render_figure(view, primary, secondary, fig_w, theme, lit=lit)
        for view in ("front", "back") for lit in (False, True)
    }
    fig_h = figs[("front", True)].height
    inner_w = 2 * fig_w + pad
    draw_chips, chips_h = _chips(primary, secondary, theme, inner_w, scale)
    w = inner_w + 2 * pad
    h = pad + label_h + fig_h + pad + chips_h + (pad if chips_h else 0)
    label_font = load_font(round(20 * scale), True, theme.font)

    def card(lit: bool) -> Image.Image:
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=round(28 * scale), fill=theme.card)
        for i, view in enumerate(("front", "back")):
            fx = pad + i * (fig_w + pad)
            lw, lh, ly = _text_size(d, view.upper(), label_font)
            d.text((fx + (fig_w - lw) // 2, pad - ly), view.upper(), font=label_font, fill=theme.muted)
            img.alpha_composite(figs[(view, lit)], (fx, pad + label_h))
        # Chips go on their own layer: ImageDraw replaces pixels rather than blending,
        # so drawing translucent chips straight onto the card would punch holes in it.
        chips = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw_chips(ImageDraw.Draw(chips), pad, pad + label_h + fig_h + pad)
        img.alpha_composite(chips)
        return img

    base, lit = _to_bgra(card(False)), _to_bgra(card(True))
    x = {"left": SAFE_LEFT, "right": CANVAS_W - SAFE_RIGHT - w, "center": (CANVAS_W - w) // 2}[x_pos]
    return Sprite(x, y, base, lit - base)


def build_overlay(
    title: str,
    subtitle: str | None,
    primary: Sequence[str],
    secondary: Sequence[str],
    theme: Theme,
    position: str = "left",
    scale: float = 1.0,
) -> list[Sprite]:
    if position not in POSITIONS:
        raise ValueError(f"position must be one of {POSITIONS}")
    title_sp = _title_sprite(title, subtitle, theme, CANVAS_W - 2 * SAFE_LEFT)
    card_y = title_sp.y + title_sp.size[1] + 28
    # Shrink the card until it fits above Instagram's caption area.
    while True:
        card = _card_sprite(primary, secondary, theme, scale, position, card_y)
        if card_y + card.size[1] <= CANVAS_H - SAFE_BOTTOM or scale <= 0.5:
            break
        scale -= 0.05
    return [title_sp, card]


def composite(frame: np.ndarray, sprites: Sequence[Sprite], glow: float, opacity: float) -> None:
    """Blend sprites onto a BGR uint8 frame in place.

    glow:    0 = muscles at rest, 1 = fully lit
    opacity: overall fade of the overlay (0..1)
    """
    if opacity <= 0:
        return
    fh, fw = frame.shape[:2]
    for sp in sprites:
        w, h = sp.size
        x0, y0 = max(sp.x, 0), max(sp.y, 0)
        x1, y1 = min(sp.x + w, fw), min(sp.y + h, fh)
        if x0 >= x1 or y0 >= y1:
            continue
        src = sp.base if sp.delta is None else sp.base + sp.delta * glow
        src = src[y0 - sp.y:y1 - sp.y, x0 - sp.x:x1 - sp.x]
        a = src[..., 3:4] * (opacity / 255.0)
        roi = frame[y0:y1, x0:x1].astype(np.float32)
        roi += (src[..., :3] - roi) * a
        frame[y0:y1, x0:x1] = np.clip(roi, 0, 255).astype(np.uint8)
