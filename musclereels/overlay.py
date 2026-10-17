"""Builds the on-screen graphics (title, body figures, legend) and blends them onto frames.

Every element is rasterised into a Sprite. The app preview and the export use the same sprites,
so what you see while editing is what gets rendered.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .bodymap import H as FIG_H, W as FIG_W, display_name, render_figure, resolve_muscles
from .layout import (CANVAS_H, CANVAS_W, ELEMENTS, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT, SAFE_TOP,
                     ElementPlacement, Layout, builtin_presets, effective_layout, snap_to_safe_zone)
from .theme import Theme, load_font

POSITIONS = ("left", "right", "center")
CARD_GAP = 28           # space between title and card in card mode


@dataclass
class Sprite:
    """A pre-rendered overlay piece. `delta` = lit - base, None for static pieces."""
    x: int
    y: int
    base: np.ndarray          # float32 BGRA, 0..255
    delta: np.ndarray | None
    name: str = ""

    @property
    def size(self) -> tuple[int, int]:
        h, w = self.base.shape[:2]
        return w, h

    @property
    def box(self) -> tuple[int, int, int, int]:
        w, h = self.size
        return self.x, self.y, self.x + w, self.y + h


def _to_bgra(img: Image.Image) -> np.ndarray:
    a = np.asarray(img.convert("RGBA"), dtype=np.float32)
    return np.ascontiguousarray(a[..., [2, 1, 0, 3]])


def _text_size(draw: ImageDraw.ImageDraw, text: str, font, stroke: int = 0) -> tuple[int, int, int]:
    x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    return x1 - x0, y1 - y0, y0


# --- title -------------------------------------------------------------------------

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
    return Sprite((CANVAS_W - w) // 2, SAFE_TOP, _to_bgra(img), None, "title")


# --- legend chips ------------------------------------------------------------------

def _chips(primary: Sequence[str], secondary: Sequence[str], theme: Theme, max_w: int, scale: float):
    """Lay out legend chips; returns (draw_fn, height, used_width)."""
    font = load_font(round(26 * scale), True, theme.font)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    ch, pad_x, dot, gap = round(44 * scale), round(14 * scale), round(14 * scale), round(10 * scale)
    items = [(m, theme.primary) for m in primary] + [(m, theme.secondary) for m in secondary]
    placed, x, y, used = [], 0, 0, 0
    for m, color in items:
        label = display_name(m)
        tw, th, ty = _text_size(probe, label, font)
        cw = pad_x + dot + gap + tw + pad_x
        if x and x + cw > max_w:
            x, y = 0, y + ch + gap
        placed.append((x, y, cw, label, color, th, ty))
        used = max(used, x + cw)
        x += cw + gap
    height = (y + ch) if placed else 0

    def draw(d: ImageDraw.ImageDraw, ox: int, oy: int) -> None:
        for cx, cy, cw, label, color, th, ty in placed:
            x0, y0 = ox + cx, oy + cy
            d.rounded_rectangle((x0, y0, x0 + cw, y0 + ch), radius=ch // 2, fill=(255, 255, 255, 22))
            dy = y0 + (ch - dot) // 2
            d.ellipse((x0 + pad_x, dy, x0 + pad_x + dot, dy + dot), fill=color)
            d.text((x0 + pad_x + dot + gap, y0 + (ch - th) // 2 - ty), label, font=font, fill=theme.text)

    return draw, height, used


# --- card mode (v0.1 look) ---------------------------------------------------------

def _card_geometry(n_views: int, show_legend: bool, primary, secondary, theme, scale, labels=True):
    fig_w = round(210 * scale)
    pad = round(22 * scale)
    label_h = round(34 * scale) if labels else 0
    fig_h = round(FIG_H * fig_w / FIG_W)
    inner_w = max(1, n_views * fig_w + max(0, n_views - 1) * pad)
    if show_legend:
        draw_chips, chips_h, _ = _chips(primary, secondary, theme, inner_w, scale)
    else:
        draw_chips, chips_h = (lambda d, x, y: None), 0
    figs_h = (label_h + fig_h) if n_views else 0
    w = inner_w + 2 * pad
    h = pad + figs_h + (pad if n_views else 0) + chips_h + (pad if chips_h else 0)
    return dict(fig_w=fig_w, pad=pad, label_h=label_h, fig_h=fig_h, inner_w=inner_w, w=w, h=h,
                draw_chips=draw_chips, chips_h=chips_h)


def _card_x(x_pos: str, w: int) -> int:
    return {"left": SAFE_LEFT, "right": CANVAS_W - SAFE_RIGHT - w, "center": (CANVAS_W - w) // 2}[x_pos]


def _card_sprite(primary, secondary, theme: Theme, scale: float, x_pos: str, y: int,
                 views: Sequence[str] = ("front", "back"), show_legend: bool = True, labels: bool = True) -> Sprite:
    g = _card_geometry(len(views), show_legend, primary, secondary, theme, scale, labels)
    fig_w, pad, label_h, w, h = g["fig_w"], g["pad"], g["label_h"], g["w"], g["h"]
    figs = {(view, lit): render_figure(view, primary, secondary, fig_w, theme, lit=lit)
            for view in views for lit in (False, True)}
    label_font = load_font(round(20 * scale), True, theme.font)

    def card(lit: bool) -> Image.Image:
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=round(28 * scale), fill=theme.card)
        for i, view in enumerate(views):
            fx = pad + i * (fig_w + pad)
            if labels:
                lw, lh, ly = _text_size(d, view.upper(), label_font)
                d.text((fx + (fig_w - lw) // 2, pad - ly), view.upper(), font=label_font, fill=theme.muted)
            img.alpha_composite(figs[(view, lit)], (fx, pad + label_h))
        # Chips go on their own layer: ImageDraw replaces pixels rather than blending,
        # so drawing translucent chips straight onto the card would punch holes in it.
        chips = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        chips_y = pad + ((label_h + g["fig_h"] + pad) if views else 0)
        g["draw_chips"](ImageDraw.Draw(chips), pad, chips_y)
        img.alpha_composite(chips)
        return img

    base, lit = _to_bgra(card(False)), _to_bgra(card(True))
    return Sprite(_card_x(x_pos, w), y, base, lit - base, "card")


def _card_mode_sprites(title, subtitle, primary, secondary, theme, layout: Layout, scale: float) -> list[Sprite]:
    sprites: list[Sprite] = []
    card_y = SAFE_TOP
    if layout.title.visible:
        title_sp = _title_sprite(title, subtitle, theme, CANVAS_W - 2 * SAFE_LEFT)
        sprites.append(title_sp)
        card_y = title_sp.y + title_sp.size[1] + CARD_GAP
    views = tuple(v for v in ("front", "back") if layout.placement(v).visible)
    if not views and not layout.legend.visible:
        return sprites
    # Shrink the card until it fits above Instagram's caption area.
    while True:
        card = _card_sprite(primary, secondary, theme, scale, layout.card_position, card_y,
                            views, layout.legend.visible, layout.labels)
        if card_y + card.size[1] <= CANVAS_H - SAFE_BOTTOM or scale <= 0.5:
            break
        scale -= 0.05
    sprites.append(card)
    return sprites


def _card_fit_scale(title, subtitle, primary, secondary, theme, layout: Layout, scale: float) -> tuple[float, int]:
    """Scale and y the card ends up with in card mode (mirrors _card_mode_sprites)."""
    card_y = SAFE_TOP
    if layout.title.visible:
        t = _title_sprite(title, subtitle, theme, CANVAS_W - 2 * SAFE_LEFT)
        card_y = t.y + t.size[1] + CARD_GAP
    n = sum(layout.placement(v).visible for v in ("front", "back"))
    while True:
        g = _card_geometry(n, layout.legend.visible, primary, secondary, theme, scale, layout.labels)
        if card_y + g["h"] <= CANVAS_H - SAFE_BOTTOM or scale <= 0.5:
            return scale, card_y
        scale -= 0.05


def materialize_card(project, segment, layout: Layout) -> Layout:
    """Turn a card-mode layout into an equivalent free layout for this segment (used before dragging)."""
    primary, secondary = segment_muscles(segment)
    scale, card_y = _card_fit_scale(segment.title, segment.subtitle, primary, secondary, project.theme,
                                    layout, project.card_scale)
    views = [v for v in ("front", "back") if layout.placement(v).visible]
    g = _card_geometry(len(views), layout.legend.visible, primary, secondary, project.theme, scale, layout.labels)
    cx = _card_x(layout.card_position, g["w"])
    pad, fig_w = g["pad"], g["fig_w"]
    pl = {"title": ElementPlacement(layout.title.visible, SAFE_LEFT, SAFE_TOP, CANVAS_W - 2 * SAFE_LEFT)}
    for v in ("front", "back"):
        i = views.index(v) if v in views else 0
        pl[v] = ElementPlacement(v in views, cx + pad + i * (fig_w + pad), card_y + pad, fig_w)
    legend_y = card_y + pad + ((g["label_h"] + g["fig_h"] + pad) if views else 0)
    pl["legend"] = ElementPlacement(layout.legend.visible, cx + pad, legend_y, g["inner_w"])
    return Layout(mode="free", card="grouped", labels=layout.labels, **pl)


# --- free mode ---------------------------------------------------------------------

def _figure_element(view, primary, secondary, theme: Theme, width: int, style: str, labels: bool,
                    x: int, y: int) -> Sprite:
    per = style == "per_element"
    s = width / (254 if per else 210)
    pad = round(22 * s) if per else 0
    fig_w = max(20, width - 2 * pad)
    label_h = round(34 * s) if labels else 0
    fig_h = round(FIG_H * fig_w / FIG_W)
    w, h = width, pad + label_h + fig_h + pad
    label_font = load_font(max(8, round(20 * s)), True, theme.font)

    def draw(lit: bool) -> Image.Image:
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if per:
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=round(28 * s), fill=theme.card)
        if labels:
            lw, lh, ly = _text_size(d, view.upper(), label_font)
            d.text((pad + (fig_w - lw) // 2, pad - ly), view.upper(), font=label_font, fill=theme.muted)
        img.alpha_composite(render_figure(view, primary, secondary, fig_w, theme, lit=lit), (pad, pad + label_h))
        return img

    base, lit = _to_bgra(draw(False)), _to_bgra(draw(True))
    return Sprite(x, y, base, lit - base, view)


def _legend_element(primary, secondary, theme: Theme, width: int, style: str, x: int, y: int) -> Sprite | None:
    per = style == "per_element"
    pad = 22 if per else 0
    draw_chips, chips_h, used = _chips(primary, secondary, theme, max(60, width - 2 * pad), 1.0)
    if not chips_h:
        return None
    w = width if per else max(1, used)
    h = chips_h + 2 * pad
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if per:
        ImageDraw.Draw(img).rounded_rectangle((0, 0, w - 1, h - 1), radius=28, fill=theme.card)
    chips = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_chips(ImageDraw.Draw(chips), pad, pad)
    img.alpha_composite(chips)
    return Sprite(x, y, _to_bgra(img), None, "legend")


def _panel_sprite(boxes: list[tuple[int, int, int, int]], theme: Theme, pad: int = 22) -> Sprite:
    x0 = min(b[0] for b in boxes) - pad
    y0 = min(b[1] for b in boxes) - pad
    x1 = max(b[2] for b in boxes) + pad
    y1 = max(b[3] for b in boxes) + pad
    img = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), radius=28, fill=theme.card)
    return Sprite(x0, y0, _to_bgra(img), None, "card")


def _free_mode_sprites(title, subtitle, primary, secondary, theme, layout: Layout) -> list[Sprite]:
    sprites: list[Sprite] = []
    if layout.title.visible:
        p = layout.title
        t = _title_sprite(title, subtitle, theme, max(100, p.width))
        sprites.append(replace(t, x=p.x + (p.width - t.size[0]) // 2, y=p.y))
    body: list[Sprite] = []
    for v in ("front", "back"):
        p = layout.placement(v)
        if p.visible:
            body.append(_figure_element(v, primary, secondary, theme, max(40, p.width), layout.card,
                                        layout.labels, p.x, p.y))
    if layout.legend.visible:
        p = layout.legend
        leg = _legend_element(primary, secondary, theme, max(60, p.width), layout.card, p.x, p.y)
        if leg:
            body.append(leg)
    # Heights depend on the content (e.g. legend rows), so keep each element inside the safe zone
    # with its real size unless the user deliberately placed it outside.
    for i, sp in enumerate(body):
        p = layout.placement(sp.name)
        snapped = snap_to_safe_zone(replace(p, x=sp.x, y=sp.y), sp.size)
        body[i] = replace(sp, x=snapped.x, y=snapped.y)
    if layout.card == "grouped" and body:
        sprites.append(_panel_sprite([s.box for s in body], theme))
    return sprites + body


# --- public API --------------------------------------------------------------------

def segment_muscles(segment) -> tuple[list[str], list[str]]:
    """Primary/secondary muscles for a segment after its click overrides."""
    primary, secondary = list(segment.primary), list(segment.secondary)
    for ref, state in (getattr(segment, "overrides", None) or {}).items():
        for m in resolve_muscles([ref]):
            primary = [x for x in primary if x != m]
            secondary = [x for x in secondary if x != m]
            if state == "primary":
                primary.append(m)
            elif state == "secondary":
                secondary.append(m)
    return primary, secondary


def _scale_sprite(sp: Sprite, s: float) -> Sprite:
    w, h = sp.size
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    base = cv2.resize(sp.base, (nw, nh), interpolation=cv2.INTER_AREA)
    delta = None if sp.delta is None else cv2.resize(sp.delta, (nw, nh), interpolation=cv2.INTER_AREA)
    return Sprite(round(sp.x * s), round(sp.y * s), base, delta, sp.name)


def build_sprites(project, segment, layout: Layout | None = None, scale: float = 1.0) -> list[Sprite]:
    """All overlay sprites for one segment, in draw order. scale < 1 is for the app preview."""
    layout = layout or effective_layout(project, segment)
    primary, secondary = segment_muscles(segment)
    if layout.mode == "card":
        sprites = _card_mode_sprites(segment.title, segment.subtitle, primary, secondary, project.theme,
                                     layout, project.card_scale)
    else:
        sprites = _free_mode_sprites(segment.title, segment.subtitle, primary, secondary, project.theme, layout)
    if scale != 1.0:
        sprites = [_scale_sprite(sp, scale) for sp in sprites]
    return sprites


def build_overlay(title: str, subtitle: str | None, primary: Sequence[str], secondary: Sequence[str],
                  theme: Theme, position: str = "left", scale: float = 1.0) -> list[Sprite]:
    """v0.1 API: title + card for one exercise."""
    if position not in POSITIONS:
        raise ValueError(f"position must be one of {POSITIONS}")
    layout = builtin_presets()[f"card-{position}"]
    return _card_mode_sprites(title, subtitle, list(primary), list(secondary), theme, layout, scale)


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


__all__ = ["Sprite", "build_sprites", "build_overlay", "composite", "materialize_card", "segment_muscles",
           "CANVAS_W", "CANVAS_H", "SAFE_TOP", "SAFE_BOTTOM", "SAFE_LEFT", "SAFE_RIGHT", "POSITIONS", "ELEMENTS"]
