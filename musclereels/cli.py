"""Command line interface: `musclereels <command>`.

Exit codes: 0 ok, 1 render/ffmpeg failure, 2 usage or validation error.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import cv2
import numpy as np

from . import __version__
from .bodymap import ALIASES, MUSCLES, display_name
from .exercises import ExerciseDB
from .layout import LayoutError, builtin_presets, resolve_preset
from .overlay import POSITIONS
from .project import FITS, Project, ProjectError, load_project, make_segment, parse_time
from .render import RenderCancelled, RenderError, render, render_still
from .theme import Theme
from .video import VideoError


class UsageError(Exception):
    pass


def _layout_from_args(args, default=None):
    if getattr(args, "layout_preset", None):
        return resolve_preset(args.layout_preset)
    if getattr(args, "position", None):
        return builtin_presets()[f"card-{args.position}"]
    return default


def _quick_project(args) -> Project:
    db = ExerciseDB(args.exercises_file or [])
    spec = {"exercise": args.exercise, "start": args.start, "end": args.end, "subtitle": args.subtitle}
    if args.title:
        spec["title"] = args.title
    seg = make_segment(spec, db)
    inp = Path(args.input)
    project = Project(input=inp, output=Path(args.output) if args.output else None, segments=[seg],
                      layout=_layout_from_args(args, builtin_presets()["card-left"]),
                      fit=args.fit or "auto", trim_to_segments=args.trim, card_scale=args.scale or 1.0,
                      exercises_file=[Path(f) for f in args.exercises_file or []])
    project.validate()
    return project


def cmd_render(args) -> None:
    if str(args.input).lower().endswith((".yaml", ".yml")):
        project = load_project(args.input, {"fit": args.fit, "card_scale": args.scale,
                                            "trim": True if args.trim else None})
        if args.output:
            project.output = Path(args.output)
        project.layout = _layout_from_args(args, project.layout)
    else:
        if not args.exercise:
            raise UsageError("Pass an exercise with -e (e.g. -e squat), or give a .yaml edit script.")
        project = _quick_project(args)
    print(f"→ {Path(project.input).name}: {len(project.segments)} segment(s)", file=sys.stderr)
    out = render(project, verbose=True)
    print(f"✓ Saved {out}")


def cmd_preview(args) -> None:
    db = ExerciseDB(args.exercises_file or [])
    spec = {"exercise": args.exercise, "subtitle": args.subtitle}
    if args.title:
        spec["title"] = args.title
    seg = make_segment(spec, db)
    project = Project(input=Path("."), output=Path(args.output), segments=[seg],
                      layout=_layout_from_args(args, builtin_presets()["card-left"]),
                      fit=args.fit or "auto", card_scale=args.scale or 1.0, theme=Theme())
    frame = None
    if args.video:
        cap = cv2.VideoCapture(args.video)
        cap.set(cv2.CAP_PROP_POS_MSEC, parse_time(args.at) * 1000)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise UsageError(f"Could not read a frame from {args.video} at {args.at}")
    img = render_still(project, seg, frame)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(args.output, img)
    print(f"✓ Saved {args.output}")


def cmd_list(args) -> None:
    if args.presets:
        for name, lay in builtin_presets().items():
            desc = f"card, {lay.card_position}" if lay.mode == "card" else f"free, card: {lay.card}"
            print(f"  {name:<18} {desc}")
        return
    if args.muscles:
        for k, v in MUSCLES.items():
            print(f"  {k:<12} {v['name']}")
        print("\nAliases: " + ", ".join(f"{a} → {'+'.join(m)}" for a, m in ALIASES.items()))
        return
    db = ExerciseDB(args.exercises_file or [])
    for ex in db.all():
        p = ", ".join(display_name(m) for m in ex.primary)
        s = ", ".join(display_name(m) for m in ex.secondary)
        print(f"  {ex.key:<24} {p}" + (f"  (+ {s})" if s else ""))


def cmd_demo(args) -> None:
    """Generate a synthetic clip and render it, to check the install end to end."""
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    clip = out_dir / "demo_clip.mp4"
    fps, secs, w, h = 30, 8, 720, 1280
    writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for i in range(fps * secs):
        t = i / fps
        img = np.zeros((h, w, 3), np.uint8)
        img[:] = (40 + 20 * math.sin(t), 30, 50 + 20 * math.cos(t))
        cy = int(h * 0.6 + 120 * math.sin(2 * math.pi * t / 2))
        cv2.circle(img, (w // 2, cy), 80, (200, 200, 200), -1)
        cv2.putText(img, "YOUR CLIP HERE", (w // 2 - 210, h - 200), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255, 255, 255), 3)
        writer.write(img)
    writer.release()
    db = ExerciseDB()
    project = Project(input=clip, output=out_dir / "demo_reel.mp4",
                      segments=[make_segment({"exercise": "bench_press", "start": 0, "end": 4, "subtitle": "4 x 8"}, db),
                                make_segment({"exercise": "squat", "start": 4, "end": 8, "subtitle": "5 x 5"}, db)])
    project.validate()
    print(f"✓ Saved {render(project, verbose=True)}")


def cmd_app(args) -> None:
    try:
        from .app import launch
    except ImportError:
        raise UsageError('The editor app needs extra packages: pip install "musclereels[app]"') from None
    sys.exit(launch(args.path))


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="musclereels",
                                description="Turn gym clips into Instagram Reels that show which muscles each exercise works.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--position", choices=POSITIONS, help="card position (same as --layout-preset card-<pos>)")
        sp.add_argument("--layout-preset", help="built-in preset name (see `list --presets`) or a preset .yaml")
        sp.add_argument("--fit", choices=FITS, help="cover = crop to fill, blur = letterbox on blurred bg (default: auto)")
        sp.add_argument("--scale", type=float, help="card size multiplier for card layouts, e.g. 0.8")
        sp.add_argument("--exercises-file", action="append", help="extra YAML with custom exercises")

    r = sub.add_parser("render", help="render a reel from a clip (+ -e EXERCISE) or a .yaml edit script")
    r.add_argument("input", help="video file, or .yaml edit script")
    r.add_argument("-e", "--exercise", help="exercise shown for the whole clip (quick mode)")
    r.add_argument("-o", "--output", help="output .mp4 (default: <input>_reel.mp4)")
    r.add_argument("--start", default=0, help="overlay start, seconds or m:ss (quick mode)")
    r.add_argument("--end", default=None, help="overlay end (quick mode, default: end of clip)")
    r.add_argument("--title", help="override the on-screen title")
    r.add_argument("--subtitle", help="small line under the title, e.g. '4 x 8 @ 80kg'")
    r.add_argument("--trim", action="store_true", help="cut the video to the overlay time range")
    common(r)
    r.set_defaults(func=cmd_render)

    pv = sub.add_parser("preview", help="render a single PNG to check the look")
    pv.add_argument("-e", "--exercise", required=True)
    pv.add_argument("-o", "--output", default="preview.png")
    pv.add_argument("--video", help="use a frame from this video as background")
    pv.add_argument("--at", default=0, help="timestamp of that frame")
    pv.add_argument("--title")
    pv.add_argument("--subtitle")
    common(pv)
    pv.set_defaults(func=cmd_preview)

    ls = sub.add_parser("list", help="list exercises (or --muscles / --presets)")
    ls.add_argument("--muscles", action="store_true")
    ls.add_argument("--presets", action="store_true")
    ls.add_argument("--exercises-file", action="append")
    ls.set_defaults(func=cmd_list)

    dm = sub.add_parser("demo", help="render a synthetic demo reel to test your setup")
    dm.add_argument("--output-dir", default="demo")
    dm.set_defaults(func=cmd_demo)

    ap = sub.add_parser("app", help="open the editor app (needs: pip install \"musclereels[app]\")")
    ap.add_argument("path", nargs="?", help="project .yaml or video to open")
    ap.set_defaults(func=cmd_app)

    args = p.parse_args(argv)
    try:
        args.func(args)
    except (UsageError, ProjectError, LayoutError, KeyError, ValueError, FileNotFoundError, VideoError) as e:
        print(f"error: {e.args[0] if e.args else e}", file=sys.stderr)
        sys.exit(2)
    except (RenderError, RenderCancelled) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
