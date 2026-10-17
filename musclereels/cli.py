"""Command line interface: `musclereels <command>`."""
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
from .overlay import POSITIONS
from .project import FITS, Job, load_job, make_segment, parse_time
from .render import render, render_still
from .theme import Theme


def _quick_job(args) -> Job:
    db = ExerciseDB(args.exercises_file or [])
    spec = {"exercise": args.exercise, "start": args.start, "end": args.end, "subtitle": args.subtitle}
    if args.title:
        spec["title"] = args.title
    seg = make_segment(spec, db)
    inp = Path(args.input)
    job = Job(input=inp, output=Path(args.output or inp.with_name(inp.stem + "_reel.mp4")),
              segments=[seg], position=args.position or "left", fit=args.fit or "auto",
              trim=args.trim, card_scale=args.scale or 1.0)
    job.validate()
    return job


def cmd_render(args) -> None:
    if str(args.input).lower().endswith((".yaml", ".yml")):
        job = load_job(args.input, {"output": args.output, "position": args.position,
                                    "fit": args.fit, "card_scale": args.scale,
                                    "trim": True if args.trim else None})
    else:
        if not args.exercise:
            sys.exit("Pass an exercise with -e (e.g. -e squat), or give a .yaml edit script.")
        job = _quick_job(args)
    print(f"→ {job.input.name}: {len(job.segments)} segment(s)", file=sys.stderr)
    out = render(job)
    print(f"✓ Saved {out}")


def cmd_preview(args) -> None:
    db = ExerciseDB(args.exercises_file or [])
    spec = {"exercise": args.exercise, "subtitle": args.subtitle}
    if args.title:
        spec["title"] = args.title
    seg = make_segment(spec, db)
    job = Job(input=Path("."), output=Path(args.output), segments=[seg],
              position=args.position or "left", fit=args.fit or "auto",
              card_scale=args.scale or 1.0, theme=Theme())
    frame = None
    if args.video:
        cap = cv2.VideoCapture(args.video)
        cap.set(cv2.CAP_PROP_POS_MSEC, parse_time(args.at) * 1000)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            sys.exit(f"Could not read a frame from {args.video} at {args.at}")
    img = render_still(job, seg, frame)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(args.output, img)
    print(f"✓ Saved {args.output}")


def cmd_list(args) -> None:
    db = ExerciseDB(args.exercises_file or [])
    if args.muscles:
        for k, v in MUSCLES.items():
            print(f"  {k:<12} {v['name']}")
        print("\nAliases: " + ", ".join(f"{a} → {'+'.join(m)}" for a, m in ALIASES.items()))
        return
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
    job = Job(input=clip, output=out_dir / "demo_reel.mp4",
              segments=[make_segment({"exercise": "bench_press", "start": 0, "end": 4, "subtitle": "4 x 8"}, db),
                        make_segment({"exercise": "squat", "start": 4, "end": 8, "subtitle": "5 x 5"}, db)])
    job.validate()
    print(f"✓ Saved {render(job)}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="musclereels",
                                description="Turn gym clips into Instagram Reels that show which muscles each exercise works.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--position", choices=POSITIONS, help="where the body-map card sits (default: left)")
        sp.add_argument("--fit", choices=FITS, help="cover = crop to fill, blur = letterbox on blurred bg (default: auto)")
        sp.add_argument("--scale", type=float, help="body-map card size multiplier, e.g. 0.8")
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

    ls = sub.add_parser("list", help="list exercises (or --muscles)")
    ls.add_argument("--muscles", action="store_true")
    ls.add_argument("--exercises-file", action="append")
    ls.set_defaults(func=cmd_list)

    dm = sub.add_parser("demo", help="render a synthetic demo reel to test your setup")
    dm.add_argument("--output-dir", default="demo")
    dm.set_defaults(func=cmd_demo)

    args = p.parse_args(argv)
    try:
        args.func(args)
    except (KeyError, ValueError, FileNotFoundError) as e:
        sys.exit(f"error: {e.args[0] if e.args else e}")


if __name__ == "__main__":
    main()
