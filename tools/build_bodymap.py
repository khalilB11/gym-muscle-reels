"""Build the detailed body-map data from the editable SVG.

    python tools/build_bodymap.py [assets/bodymap.svg]

Reads every <polygon>/<path> whose id is "<view>-<muscle_id>[-n]" inside <g id="front"> / <g id="back">,
flattens curves, removes the group's offset, mirrors each shape across x = 100 and writes
musclereels/data/bodymap/front.json and back.json. Fails if a muscle in muscles.yaml has no shape
in a view it lists, or a shape uses an unknown id. (Dev-only dependency: svgelements.)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "musclereels" / "data" / "bodymap"
W = 200
OFFSETS = {"front": 0.0, "back": 220.0}       # x offset of each <g> in the SVG canvas


def load_svg(path: Path) -> dict[str, dict[str, list]]:
    from svgelements import SVG, Path as SvgPath, Polygon, Shape

    svg = SVG.parse(str(path), reify=True)
    regions: dict[str, dict[str, list]] = {"front": {}, "back": {}}
    for el in svg.elements():
        if not isinstance(el, Shape) or not el.id:
            continue
        m = re.fullmatch(r"(front|back)-([a-z_]+?)(?:-\d+)?", el.id)
        if not m:
            continue
        view, muscle = m.groups()
        if isinstance(el, Polygon):
            pts = [(p.x, p.y) for p in el.points]
        else:
            path = SvgPath(el)
            n = max(12, int(path.length() / 1.5))
            pts = [(pt.x, pt.y) for pt in (path.point(i / n) for i in range(n))]
        pts = [(round(x - OFFSETS[view], 2), round(y, 2)) for x, y in pts]
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts = pts[:-1]
        regions[view].setdefault(muscle, []).append(pts)
    return regions


def mirrored(polys: list) -> list:
    return polys + [[(round(W - x, 2), y) for x, y in reversed(p)] for p in polys]


def main(argv=None) -> int:
    src = Path((argv or sys.argv[1:] or [str(REPO / "assets" / "bodymap.svg")])[0])
    regions = load_svg(src)
    muscles = yaml.safe_load((REPO / "musclereels" / "data" / "muscles.yaml").read_text("utf-8"))["muscles"]
    errors = []
    for view, shapes in regions.items():
        for mid in shapes:
            if mid not in muscles:
                errors.append(f"{view}: unknown muscle id '{mid}'")
    for mid, spec in muscles.items():
        for view in spec.get("views", []):
            if mid not in regions[view]:
                errors.append(f"{mid}: no shape in the {view} view")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for view, shapes in regions.items():
        data = {"view": view, "width": W, "height": 440,
                "regions": {mid: mirrored(polys) for mid, polys in shapes.items()}}
        (OUT / f"{view}.json").write_text(json.dumps(data, separators=(",", ":")), "utf-8")
        print(f"✓ {view}: {len(shapes)} muscles → {OUT / (view + '.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
