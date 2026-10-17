"""Video pipeline: decode -> reframe to 9:16 -> draw overlay -> encode with ffmpeg."""
from __future__ import annotations

import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from .overlay import CANVAS_H, CANVAS_W, Sprite, build_overlay, composite
from .project import Job, Segment

FADE_IN = 0.35     # seconds for the card to fade in / out
GLOW_DELAY = 0.15  # muscles light up just after the card appears


def require_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        sys.exit("ffmpeg not found. Install it (macOS: `brew install ffmpeg`, "
                 "Ubuntu: `sudo apt install ffmpeg`, Windows: `winget install ffmpeg`) and retry.")
    return exe


def fit_frame(frame: np.ndarray, mode: str = "auto") -> np.ndarray:
    """Reframe any clip to 1080x1920.

    cover: fill the screen, cropping the edges (best for vertical clips)
    blur:  whole clip centred over a blurred, zoomed copy (best for landscape)
    """
    h, w = frame.shape[:2]
    if mode == "auto":
        mode = "cover" if w / h <= 0.75 else "blur"

    def resize(img, s):
        nw, nh = max(1, round(img.shape[1] * s)), max(1, round(img.shape[0] * s))
        return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)

    def cover(img, W, H):
        r = resize(img, max(W / img.shape[1], H / img.shape[0]))
        y, x = (r.shape[0] - H) // 2, (r.shape[1] - W) // 2
        return r[y:y + H, x:x + W]

    if mode == "cover":
        return np.ascontiguousarray(cover(frame, CANVAS_W, CANVAS_H))

    small = cover(frame, CANVAS_W // 8, CANVAS_H // 8)
    bg = cv2.GaussianBlur(small, (0, 0), 6)
    bg = cv2.resize(bg, (CANVAS_W, CANVAS_H), interpolation=cv2.INTER_LINEAR)
    out = (bg.astype(np.float32) * 0.55).astype(np.uint8)
    fg = resize(frame, min(CANVAS_W / w, CANVAS_H / h))
    y, x = (CANVAS_H - fg.shape[0]) // 2, (CANVAS_W - fg.shape[1]) // 2
    out[y:y + fg.shape[0], x:x + fg.shape[1]] = fg
    return out


def envelope(t: float, seg: Segment, pulse_hz: float) -> tuple[float, float]:
    """(glow, opacity) for time t inside a segment."""
    into, left = t - seg.start, seg.end - t
    opacity = min(1.0, into / FADE_IN, left / FADE_IN if math.isfinite(left) else 1.0)
    ramp = min(1.0, max(0.0, (into - GLOW_DELAY) / 0.4))
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * pulse_hz * into - math.pi / 2)
    return ramp * (0.7 + 0.3 * pulse), max(0.0, opacity)


def build_sprites(job: Job, seg: Segment) -> list[Sprite]:
    return build_overlay(seg.title, seg.subtitle, seg.primary, seg.secondary,
                         job.theme, job.position, job.card_scale)


def _has_audio(path: Path) -> bool:
    probe = shutil.which("ffprobe")
    if not probe:
        return True  # let ffmpeg's optional mapping (`1:a:0?`) handle it
    r = subprocess.run([probe, "-v", "error", "-select_streams", "a", "-show_entries",
                        "stream=index", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return bool(r.stdout.strip())


def render(job: Job, progress: bool = True) -> Path:
    ffmpeg = require_ffmpeg()
    if not job.input.exists():
        sys.exit(f"Input video not found: {job.input}")
    cap = cv2.VideoCapture(str(job.input))
    if not cap.isOpened():
        sys.exit(f"Could not open video: {job.input}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    duration = total / fps if total else math.inf

    t_start = job.segments[0].start if job.trim else 0.0
    t_end = min(job.segments[-1].end, duration) if job.trim else duration

    job.output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{CANVAS_W}x{CANVAS_H}",
           "-r", f"{fps:.6f}", "-i", "-"]
    audio = job.audio and _has_audio(job.input)
    if audio:
        if t_start > 0:
            cmd += ["-ss", f"{t_start:.3f}"]
        if math.isfinite(t_end):
            cmd += ["-to", f"{t_end:.3f}"]
        cmd += ["-i", str(job.input), "-map", "0:v:0", "-map", "1:a:0?", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", job.preset, "-crf", str(job.crf),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(job.output)]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    cache: dict[int, list[Sprite]] = {}
    seg_i, idx, written, t0, last = 0, 0, 0, time.time(), 0.0
    n_out = round((t_end - t_start) * fps) if math.isfinite(t_end) else total
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t = idx / fps
            idx += 1
            if t < t_start - 1e-6:
                continue
            if t > t_end + 1e-6:
                break
            out = fit_frame(frame, job.fit)
            while seg_i < len(job.segments) and t >= job.segments[seg_i].end:
                cache.pop(seg_i, None)  # free memory of finished segments
                seg_i += 1
            if seg_i < len(job.segments) and t >= job.segments[seg_i].start:
                seg = job.segments[seg_i]
                if seg_i not in cache:
                    cache[seg_i] = build_sprites(job, seg)
                glow, opacity = envelope(t, seg, job.pulse_hz)
                composite(out, cache[seg_i], glow, opacity)
            enc.stdin.write(out.tobytes())
            written += 1
            if progress and time.time() - last > 0.5:
                last = time.time()
                pct = f"{100 * written / n_out:5.1f}%" if n_out else f"{written} frames"
                print(f"\r  rendering {pct}  ({written / (last - t0):.0f} fps)", end="", file=sys.stderr)
    finally:
        cap.release()
        enc.stdin.close()
        code = enc.wait()
    if progress:
        print(f"\r  rendered {written} frames in {time.time() - t0:.1f}s" + " " * 20, file=sys.stderr)
    if code != 0:
        sys.exit(f"ffmpeg failed with exit code {code}")
    return job.output


def render_still(job: Job, seg: Segment, frame: np.ndarray | None = None) -> np.ndarray:
    """One fully-lit frame for quick previews."""
    if frame is None:
        g = np.linspace(40, 10, CANVAS_H, dtype=np.float32)[:, None, None]
        canvas = np.broadcast_to(g, (CANVAS_H, CANVAS_W, 3)).astype(np.uint8).copy()
    else:
        canvas = fit_frame(frame, job.fit)
    composite(canvas, build_sprites(job, seg), glow=1.0, opacity=1.0)
    return canvas
