"""Where overlay elements sit on the 1080x1920 canvas.

Two layout modes:
  card  - the v0.1 look: title on top, one card with both figures + legend, placed
          left/right/center. Geometry is computed per segment (it depends on the text).
  free  - every element (title, front, back, legend) has its own box in canvas pixels.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Optional

import yaml

CANVAS_W, CANVAS_H = 1080, 1920
# Areas Instagram covers with its own UI (header, caption, action buttons).
SAFE_TOP, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT = 250, 450, 60, 180
SAFE_RECT = (SAFE_LEFT, SAFE_TOP, CANVAS_W - SAFE_RIGHT, CANVAS_H - SAFE_BOTTOM)  # x0, y0, x1, y1

ELEMENTS = ("title", "front", "back", "legend", "tiles")   # tiles = one zoomed box per muscle
MODES = ("card", "free")
CARD_POSITIONS = ("left", "right", "center")
CARD_STYLES = ("grouped", "per_element", "none")
_PLACEMENT_KEYS = {"visible", "x", "y", "width", "allow_outside_safe_zone"}


class LayoutError(ValueError):
    pass


@dataclass(frozen=True)
class ElementPlacement:
    """Box of one element in canvas px. Height follows from the element's content/aspect."""
    visible: bool = True
    x: int = 0
    y: int = 0
    width: int = 0
    allow_outside_safe_zone: bool = False

    def to_dict(self) -> dict:
        d = {"visible": self.visible, "x": self.x, "y": self.y, "width": self.width}
        if self.allow_outside_safe_zone:
            d["allow_outside_safe_zone"] = True
        return d

    def merged(self, partial: dict) -> "ElementPlacement":
        bad = set(partial) - _PLACEMENT_KEYS
        if bad:
            raise LayoutError(f"unknown placement key(s): {', '.join(sorted(bad))}")
        conv = {k: (bool(v) if k in ("visible", "allow_outside_safe_zone") else int(round(float(v))))
                for k, v in partial.items()}
        return replace(self, **conv)


# Defaults used when a free layout omits an element.
_FREE_DEFAULTS = {
    "title": ElementPlacement(True, SAFE_LEFT, SAFE_TOP, CANVAS_W - 2 * SAFE_LEFT),
    "front": ElementPlacement(True, SAFE_LEFT, 520, 220),
    "back": ElementPlacement(True, SAFE_LEFT + 260, 520, 220),
    "legend": ElementPlacement(True, SAFE_LEFT, 1100, 520),
    "tiles": ElementPlacement(False, SAFE_LEFT, 520, 840),
}
_HIDDEN = ElementPlacement(visible=False)


@dataclass(frozen=True)
class Layout:
    mode: str = "card"
    card_position: str = "left"            # card mode only
    card: str = "grouped"                  # free mode: grouped | per_element | none
    labels: bool = True                    # FRONT / BACK captions
    title: ElementPlacement = field(default_factory=ElementPlacement)
    front: ElementPlacement = field(default_factory=ElementPlacement)
    back: ElementPlacement = field(default_factory=ElementPlacement)
    legend: ElementPlacement = field(default_factory=ElementPlacement)
    tiles: ElementPlacement = field(default_factory=lambda: _HIDDEN)   # off unless asked for
    tile_names: bool = True                # muscle name under each tile

    def __post_init__(self):
        if self.mode not in MODES:
            raise LayoutError(f"layout mode must be one of {MODES}")
        if self.card_position not in CARD_POSITIONS:
            raise LayoutError(f"card position must be one of {CARD_POSITIONS}")
        if self.card not in CARD_STYLES:
            raise LayoutError(f"card must be one of {CARD_STYLES}")

    def placement(self, name: str) -> ElementPlacement:
        return getattr(self, name)

    def to_dict(self) -> dict:
        if self.mode == "card":
            d: dict = {"mode": "card", "position": self.card_position}
            if not self.labels:
                d["labels"] = False
            hidden = {n: {"visible": False} for n in ELEMENTS if n != "tiles" and not self.placement(n).visible}
            d.update(hidden)
            return d
        d = {"card": self.card, "labels": self.labels}
        d.update({n: self.placement(n).to_dict() for n in ELEMENTS if n != "tiles" or self.tiles.visible})
        if not self.tile_names:
            d["tile_names"] = False
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Layout":
        d = dict(d or {})
        allowed = {"mode", "position", "card", "labels", "tile_names", *ELEMENTS}
        bad = set(d) - allowed
        if bad:
            raise LayoutError(f"unknown layout key(s): {', '.join(sorted(bad))}")
        mode = d.get("mode", "free")
        base = {n: (_FREE_DEFAULTS[n] if mode == "free" else ElementPlacement()) for n in ELEMENTS}
        base["tiles"] = _FREE_DEFAULTS["tiles"] if mode == "free" else _HIDDEN
        placements = {n: base[n].merged(d.get(n) or {}) for n in ELEMENTS}
        if "tiles" in d and "visible" not in (d.get("tiles") or {}):
            placements["tiles"] = replace(placements["tiles"], visible=True)   # listing tiles turns them on
        return cls(mode=mode, card_position=d.get("position", "left"), card=d.get("card", "grouped"),
                   labels=bool(d.get("labels", True)), tile_names=bool(d.get("tile_names", True)), **placements)


@dataclass
class SegmentLayoutOverride:
    """Partial layout for one segment: only the given fields replace the project default."""
    elements: dict[str, dict] = field(default_factory=dict)
    card: Optional[str] = None
    labels: Optional[bool] = None

    @classmethod
    def from_dict(cls, d: dict) -> "SegmentLayoutOverride":
        d = dict(d or {})
        bad = set(d) - {"card", "labels", *ELEMENTS}
        if bad:
            raise LayoutError(f"unknown layout override key(s): {', '.join(sorted(bad))}")
        elements = {}
        for n in ELEMENTS:
            if n in d:
                part = dict(d[n] or {})
                ElementPlacement().merged(part)  # validates keys
                elements[n] = part
        card = d.get("card")
        if card is not None and card not in CARD_STYLES:
            raise LayoutError(f"card must be one of {CARD_STYLES}")
        return cls(elements, card, d.get("labels"))

    def to_dict(self) -> dict:
        d: dict = {n: dict(v) for n, v in self.elements.items()}
        if self.card is not None:
            d["card"] = self.card
        if self.labels is not None:
            d["labels"] = self.labels
        return d

    @property
    def is_geometric(self) -> bool:
        return any(k in part for part in self.elements.values() for k in ("x", "y", "width"))

    def __bool__(self) -> bool:
        return bool(self.elements) or self.card is not None or self.labels is not None


def apply_override(base: Layout, ov: SegmentLayoutOverride) -> Layout:
    changes = {n: base.placement(n).merged(part) for n, part in ov.elements.items()}
    if ov.card is not None:
        changes["card"] = ov.card
    if ov.labels is not None:
        changes["labels"] = ov.labels
    return replace(base, **changes)


def effective_layout(project, segment) -> Layout:
    """Project default layout with the segment's override applied."""
    base: Layout = project.layout
    ov: Optional[SegmentLayoutOverride] = getattr(segment, "layout", None)
    if not ov:
        return base
    if base.mode == "card" and (ov.is_geometric or ov.card is not None):
        from .overlay import materialize_card  # lazy: overlay imports this module
        base = materialize_card(project, segment, base)
    return apply_override(base, ov)


def snap_to_safe_zone(p: ElementPlacement, size: tuple[int, int]) -> ElementPlacement:
    """Clamp the element box (size = rendered w, h) inside the Instagram safe zone."""
    if p.allow_outside_safe_zone:
        return p
    w, h = size
    x0, y0, x1, y1 = SAFE_RECT
    x = min(max(p.x, x0), max(x0, x1 - w))
    y = min(max(p.y, y0), max(y0, y1 - h))
    return p if (x, y) == (p.x, p.y) else replace(p, x=x, y=y)


# --- presets -------------------------------------------------------------------

@lru_cache(maxsize=1)
def _builtin() -> dict[str, Layout]:
    text = resources.files("musclereels").joinpath("data/presets.yaml").read_text("utf-8")
    return {name: Layout.from_dict(spec) for name, spec in (yaml.safe_load(text) or {}).items()}


def builtin_presets() -> dict[str, Layout]:
    return dict(_builtin())


def preset_name(layout: Layout) -> Optional[str]:
    for name, lay in _builtin().items():
        if lay == layout:
            return name
    return None


def resolve_preset(name_or_path: str, base_dir: Path | None = None) -> Layout:
    presets = _builtin()
    if name_or_path in presets:
        return presets[name_or_path]
    p = Path(name_or_path).expanduser()
    if not p.is_absolute() and base_dir is not None:
        p = base_dir / p
    if p.suffix.lower() in (".yaml", ".yml") and p.exists():
        return load_preset(p)[1]
    raise LayoutError(f"Unknown layout preset '{name_or_path}'. Built-in: {', '.join(presets)}")


def load_preset(path: str | Path) -> tuple[str, Layout]:
    data = yaml.safe_load(Path(path).read_text("utf-8")) or {}
    if "layout" not in data:
        raise LayoutError(f"{path}: preset file needs `name` and `layout`")
    return data.get("name", Path(path).stem), Layout.from_dict(data["layout"])


def save_preset(name: str, layout: Layout, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(yaml.safe_dump({"name": name, "layout": layout.to_dict()}, sort_keys=False), "utf-8")


__all__ = ["ElementPlacement", "Layout", "SegmentLayoutOverride", "LayoutError", "effective_layout",
           "snap_to_safe_zone", "builtin_presets", "load_preset", "save_preset", "resolve_preset",
           "preset_name", "apply_override", "CANVAS_W", "CANVAS_H", "SAFE_RECT", "SAFE_TOP",
           "SAFE_BOTTOM", "SAFE_LEFT", "SAFE_RIGHT", "ELEMENTS"]
