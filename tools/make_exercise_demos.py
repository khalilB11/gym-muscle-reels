"""Render a demo reel for every exercise in the database, at Detailed level.

    python tools/make_exercise_demos.py [out/demos] [--jobs 4] [--only squat,deadlift]

Each reel (8 s, 1080x1920): 0-4 s full-body front/back figures with muscle names,
4-8 s muscle boxes (one zoomed close-up per worked muscle). The athlete is the animated
stand-in from tools/demo_athlete.py; swap `input:` for a real clip to use your own footage.
Also writes contact_sheet.png (one frame of each style per exercise).
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from demo_athlete import PATTERN_OF, make_clip  # noqa: E402

from musclereels.activation import activate  # noqa: E402
from musclereels.bodymap import display_name  # noqa: E402
from musclereels.exercises import ExerciseDB  # noqa: E402
from musclereels.layout import Layout  # noqa: E402
from musclereels.overlay import _merge_complete_groups  # noqa: E402
from musclereels.project import Project, make_segment, save_project  # noqa: E402
from musclereels.render import render  # noqa: E402
from musclereels.theme import Theme  # noqa: E402

LAYOUT = {
    "card": "per_element", "labels": True,
    "title": {"visible": True, "x": 60, "y": 250, "width": 960},
    "front": {"visible": False, "x": 60, "y": 430, "width": 220},
    "back": {"visible": False, "x": 300, "y": 430, "width": 220},
    "legend": {"visible": False, "x": 540, "y": 430, "width": 360},
    "tiles": {"visible": False, "x": 60, "y": 440, "width": 780},
}
FULL_BODY = {"front": {"visible": True}, "back": {"visible": True}, "legend": {"visible": True}}
BOXES = {"tiles": {"visible": True}}


def short_list(ids, n=3) -> str:
    names = [display_name(m) for m in _merge_complete_groups(ids)]
    return ", ".join(names[:n]) + (" +" if len(names) > n else "")


def build_project(key: str, clip: Path, out: Path) -> Project:
    db = ExerciseDB()
    ex = db.get(key)
    primary, _ = activate(ex.primary, ex.secondary, {}, "detailed")
    theme = Theme()
    theme.card = (*theme.card[:3], 115)              # ~45 % panels
    segs = [
        make_segment({"exercise": key, "start": 0, "end": 4, "subtitle": f"Main: {short_list(primary)}",
                      "layout": FULL_BODY}, db),
        make_segment({"exercise": key, "start": 4, "end": 8, "subtitle": "Every muscle, close up",
                      "layout": BOXES}, db),
    ]
    return Project(input=clip, output=out, segments=segs, layout=Layout.from_dict(LAYOUT),
                   detail_level="detailed", theme=theme, preset="veryfast", crf=20)


def render_one(args) -> str:
    key, out_dir = args
    clip = out_dir / "clips" / f"{PATTERN_OF[key]}.mp4"
    proj = build_project(key, clip, out_dir / f"{key}.mp4")
    save_project(proj, out_dir / "projects" / f"{key}.yaml")
    render(proj)
    return key


def contact_sheet(keys, out_dir: Path) -> Path:
    cells = []
    for key in keys:
        cap = cv2.VideoCapture(str(out_dir / f"{key}.mp4"))
        frames = []
        for t in (2.0, 6.0):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, f = cap.read()
            frames.append(cv2.resize(f, (216, 384)) if ok else np.zeros((384, 216, 3), np.uint8))
        cap.release()
        cells.append(np.hstack(frames))
    cols = 6
    while len(cells) % cols:
        cells.append(np.zeros_like(cells[0]))
    rows = [np.hstack([np.pad(c, ((6, 6), (6, 6), (0, 0))) for c in cells[i:i + cols]]) for i in range(0, len(cells), cols)]
    path = out_dir / "contact_sheet.png"
    cv2.imwrite(str(path), np.vstack(rows))
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", nargs="?", default="out/demos")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--only", help="comma-separated exercise keys")
    a = ap.parse_args(argv)
    out_dir = Path(a.out_dir).resolve()
    keys = [e.key for e in ExerciseDB().all()]
    if a.only:
        keys = [k.strip() for k in a.only.split(",")]
    for pattern in sorted({PATTERN_OF[k] for k in keys}):
        clip = out_dir / "clips" / f"{pattern}.mp4"
        if not clip.exists():
            make_clip(pattern, clip)
    with ProcessPoolExecutor(max_workers=a.jobs) as pool:
        for i, key in enumerate(pool.map(render_one, [(k, out_dir) for k in keys]), 1):
            print(f"[{i}/{len(keys)}] {key}", flush=True)
    print(f"✓ {contact_sheet(keys, out_dir)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
