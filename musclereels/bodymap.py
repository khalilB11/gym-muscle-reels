"""Vector body map: front and back figures split into muscle regions.

All shapes live in a 200 x 440 design space per figure. Shapes are defined for
one side of the body and mirrored, so tweaking a muscle means editing one list.
"""
from __future__ import annotations

import math
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter

from .muscles import normalize, registry  # noqa: F401  (normalize re-exported)

W, H = 200, 440

Point = tuple[float, float]
Poly = list[Point]


def _mirror(poly: Poly) -> Poly:
    return [(W - x, y) for x, y in poly]


def _pair(poly: Poly) -> list[Poly]:
    return [poly, _mirror(poly)]


def _ellipse(cx: float, cy: float, rx: float, ry: float, n: int = 32) -> Poly:
    return [
        (cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def _rect(x0: float, y0: float, x1: float, y1: float) -> Poly:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# --- shared pieces -----------------------------------------------------------
_HEAD = [_ellipse(100, 26, 17, 21)]
_NECK = [[(92, 44), (108, 44), (110, 62), (90, 62)]]
_ELBOWS = _pair(_ellipse(139, 146, 8, 7))
_HANDS = _pair(_ellipse(151, 220, 8, 13))
_KNEES = _pair(_ellipse(121, 316, 11, 12))
_FEET = _pair([(112, 404), (130, 404), (137, 420), (108, 420)])

_DELT = [(124, 64), (139, 66), (147, 80), (147, 98), (139, 104), (131, 88), (126, 74)]
_UPPER_ARM = [(132, 104), (142, 104), (148, 118), (146, 138), (138, 144), (131, 130), (130, 112)]
_FOREARM = [(134, 150), (146, 148), (154, 164), (157, 192), (152, 206), (144, 206), (138, 184), (133, 164)]

# Non-muscle filler drawn first so the figure reads as one body.
FILLERS: dict[str, list[Poly]] = {
    "front": _HEAD + _NECK
    + _pair([(100, 186), (116, 184), (128, 196), (122, 214), (108, 222), (100, 224)])
    + _ELBOWS + _HANDS + _KNEES + _FEET,
    "back": _HEAD + _NECK + _ELBOWS + _HANDS + _KNEES + _FEET,
}

# Muscle regions per view, drawn in insertion order (later overlaps earlier).
SHAPES: dict[str, dict[str, list[Poly]]] = {
    "front": {
        "traps": _pair([(108, 50), (124, 62), (112, 64)]),
        "front_delts": _pair(_DELT),
        "chest": _pair([(101, 68), (123, 66), (130, 78), (131, 92), (119, 104), (101, 102)]),
        "biceps": _pair(_UPPER_ARM),
        "forearms": _pair(_FOREARM),
        "abs": [
            p
            for r in [(102, 106, 114, 126), (102, 129, 114, 149), (102, 152, 114, 172), (102, 175, 112, 192)]
            for p in _pair(_rect(*r))
        ],
        "obliques": _pair([(117, 106), (130, 96), (134, 118), (132, 156), (125, 182), (115, 176), (116, 140)]),
        "adductors": _pair([(101, 226), (106, 224), (106, 252), (110, 284), (104, 290), (101, 262)]),
        "quads": _pair([(106, 222), (122, 214), (132, 202), (138, 230), (138, 268), (133, 296),
                        (126, 306), (116, 304), (109, 282), (105, 250)]),
        "calves": _pair([(112, 330), (130, 328), (136, 352), (134, 384), (127, 402), (118, 402),
                         (112, 380), (110, 352)]),
    },
    "back": {
        "lats": _pair([(102, 106), (114, 100), (120, 74), (132, 82), (134, 104), (130, 138),
                       (118, 166), (102, 172)]),
        "traps": _pair([(101, 46), (108, 50), (127, 63), (118, 70), (101, 70)]),
        "rhomboids": _pair([(101, 72), (118, 72), (114, 98), (101, 104)]),
        "rear_delts": _pair(_DELT),
        "triceps": _pair(_UPPER_ARM),
        "forearms": _pair(_FOREARM),
        "lower_back": _pair([(101, 140), (110, 140), (113, 186), (101, 190)]),
        "glutes": _pair([(101, 188), (118, 182), (133, 196), (136, 220), (125, 234), (107, 234), (101, 224)]),
        "hamstrings": _pair([(104, 238), (124, 238), (136, 232), (138, 266), (133, 296), (126, 306),
                             (116, 304), (109, 282)]),
        "calves": _pair([(110, 328), (132, 328), (139, 352), (135, 380), (125, 396), (117, 396),
                         (110, 372), (108, 350)]),
    },
}

# Simple group id -> the body-map regions it lights up (names/aliases live in data/muscles.yaml).
GROUP_SHAPES: dict[str, list[tuple[str, str]]] = {
    "chest":       [("front", "chest")],
    "front_delts": [("front", "front_delts")],
    "side_delts":  [("front", "front_delts"), ("back", "rear_delts")],
    "rear_delts":  [("back", "rear_delts")],
    "traps":       [("front", "traps"), ("back", "traps")],
    "rhomboids":   [("back", "rhomboids")],
    "lats":        [("back", "lats")],
    "lower_back":  [("back", "lower_back")],
    "biceps":      [("front", "biceps")],
    "triceps":     [("back", "triceps")],
    "forearms":    [("front", "forearms"), ("back", "forearms")],
    "abs":         [("front", "abs")],
    "obliques":    [("front", "obliques")],
    "glutes":      [("back", "glutes")],
    "quads":       [("front", "quads")],
    "hamstrings":  [("back", "hamstrings")],
    "adductors":   [("front", "adductors")],
    "calves":      [("front", "calves"), ("back", "calves")],
}

# Backwards-compatible views of the registry (v0.1 API).
MUSCLES: dict[str, dict] = {
    gid: {"name": registry().display_name(gid), "shapes": GROUP_SHAPES[gid]} for gid in registry().groups
}
ALIASES: dict[str, list[str]] = dict(registry().aliases)


def resolve_muscles(names: Iterable[str]) -> list[str]:
    """Expand aliases, validate, and de-duplicate (order preserved)."""
    return registry().resolve(names)


def display_name(muscle: str) -> str:
    return registry().display_name(muscle)


def _levels(view: str, primary: Iterable[str], secondary: Iterable[str]) -> dict[str, str]:
    levels: dict[str, str] = {}
    for level, muscles in (("secondary", secondary), ("primary", primary)):  # primary wins
        for m in muscles:
            for v, sid in GROUP_SHAPES[m]:
                if v == view:
                    levels[sid] = level
    return levels


def render_figure(
    view: str,
    primary: Iterable[str],
    secondary: Iterable[str],
    width_px: int,
    theme,
    lit: bool = True,
    supersample: int = 4,
) -> Image.Image:
    """Render one figure ('front' or 'back') as an RGBA image `width_px` wide.

    lit=False renders every muscle as inactive (the "resting" state); the
    compositor cross-fades between the two to animate the highlight.
    """
    s = width_px * supersample / W
    big = (round(W * s), round(H * s))
    levels = _levels(view, primary, secondary) if lit else {}
    colors = {"primary": theme.primary, "secondary": theme.secondary}
    gap = max(1, round(1.8 * s))

    def scaled(poly: Poly) -> list[Point]:
        return [(x * s, y * s) for x, y in poly]

    body = Image.new("RGBA", big, (0, 0, 0, 0))
    d = ImageDraw.Draw(body)
    for poly in FILLERS[view]:
        d.polygon(scaled(poly), fill=theme.filler, outline=theme.gap, width=gap)
    for sid, polys in SHAPES[view].items():
        fill = colors.get(levels.get(sid, ""), theme.inactive)
        for poly in polys:
            d.polygon(scaled(poly), fill=fill, outline=theme.gap, width=gap)

    if levels:
        glow = Image.new("RGBA", big, (0, 0, 0, 0))
        g = ImageDraw.Draw(glow)
        for sid, level in levels.items():
            for poly in SHAPES[view][sid]:
                g.polygon(scaled(poly), fill=colors[level])
        glow = glow.filter(ImageFilter.GaussianBlur(radius=6 * s))
        body = Image.alpha_composite(glow, body)

    return body.resize((width_px, round(H * width_px / W)), Image.LANCZOS)
