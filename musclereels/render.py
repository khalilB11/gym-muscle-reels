"""Video pipeline: decode -> reframe to 9:16 -> draw overlay -> encode with ffmpeg.

`frame_for_time` is the single function that produces an output frame. The app preview and the
export both call it, which is what keeps them identical.
"""
from __future__ import annotations

import math
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .layout import CANVAS_H, CANVAS_W, effective_layout
from .overlay import Sprite, build_sprites, composite
from .project import Project, Segment
from .video import VideoSource, ffmpeg_exe, fit_frame  # noqa: F401  (fit_frame re-exported for v0.1 API)

FADE_IN = 0.35     # seconds for the overlay to fade in / out
GLOW_DELAY = 0.15  # muscles light up just after the overlay appears

FFMPEG_HELP = ("ffmpeg not found. Install it (macOS: `brew install ffmpeg`, Ubuntu: `sudo apt install ffmpeg`, "
               "Windows: `winget install ffmpeg`) or `pip install \"musclereels[app]\"`, and retry.")


class RenderError(RuntimeError):
    pass


class RenderCancelled(RuntimeError):
    pass


def require_ffmpeg() -> str:
    exe = ffmpeg_exe()
    if not exe:
        raise RenderError(FFMPEG_HELP)
    return exe


def envelope(t: float, seg: Segment, pulse_hz: float) -> tuple[float, float]:
    """(glow, opacity) for time t inside a segment."""
    into, left = t - seg.start, seg.end - t
    opacity = min(1.0, into / FADE_IN, left / FADE_IN if math.isfinite(left) else 1.0)
    ramp = min(1.0, max(0.0, (into - GLOW_DELAY) / 0.4))
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * pulse_hz * into - math.pi / 2)
    return ramp * (0.7 + 0.3 * pulse), max(0.0, opacity)


class SpriteCache:
    """Sprites per (segment content, layout, scale); rebuilt only when something changes."""

    def __init__(self, max_items: int = 16):
        self._items: dict[tuple, list[Sprite]] = {}
        self.max_items = max_items

    def get(self, project: Project, seg: Segment, scale: float = 1.0) -> list[Sprite]:
        layout = effective_layout(project, seg)
        key = (repr(seg), repr(layout), repr(project.theme), project.card_scale, project.detail_level, scale)
        if key not in self._items:
            if len(self._items) >= self.max_items:
                self._items.pop(next(iter(self._items)))
            self._items[key] = build_sprites(project, seg, layout, scale)
        return self._items[key]

    def clear(self) -> None:
        self._items.clear()


def frame_for_time(project: Project, t: float, source_frame: Optional[np.ndarray] = None, scale: float = 1.0,
                   cache: Optional[SpriteCache] = None, video: Optional[VideoSource] = None) -> np.ndarray:
    """The output frame at time t (BGR, 1080x1920 * scale)."""
    if source_frame is None:
        source_frame = (video or VideoSource(project.input)).frame_at(t)
    size = (round(CANVAS_W * scale), round(CANVAS_H * scale))
    out = fit_frame(source_frame, project.fit, out_size=size)
    seg = project.segment_at(t)
    if seg is not None:
        sprites = (cache or SpriteCache()).get(project, seg, scale)
        glow, opacity = envelope(t, seg, project.pulse_hz)
        composite(out, sprites, glow, opacity)
    return out


def render(project: Project, progress_cb: Optional[Callable[[float], None]] = None,
           cancel: Optional[threading.Event] = None, verbose: bool = False) -> Path:
    """Render the reel to project.output. Raises RenderCancelled if `cancel` gets set."""
    ffmpeg = require_ffmpeg()
    project.validate()
    video = VideoSource(project.input)
    video.prepare()
    info = video.info
    fps = info.fps
    t_start, t_end = project.time_range(info.duration)
    n_out = max(1, round((t_end - t_start) * fps))

    output = Path(project.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{CANVAS_W}x{CANVAS_H}",
           "-r", f"{fps:.6f}", "-i", "-"]
    if project.audio and info.has_audio:
        if t_start > 0:
            cmd += ["-ss", f"{t_start:.3f}"]
        if math.isfinite(t_end):
            cmd += ["-to", f"{t_end:.3f}"]
        cmd += ["-i", str(project.input), "-map", "0:v:0", "-map", "1:a:0?", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", project.preset, "-crf", str(project.crf),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    cache = SpriteCache()
    written = 0
    cancelled = False
    try:
        for t, frame in video.iter_frames(t_start, t_end):
            if cancel is not None and cancel.is_set():
                cancelled = True
                break
            out = frame_for_time(project, t, source_frame=frame, cache=cache)
            enc.stdin.write(out.tobytes())
            written += 1
            if progress_cb:
                progress_cb(min(1.0, written / n_out))
            if verbose and written % 15 == 0:
                print(f"\r  rendering {100 * min(1.0, written / n_out):5.1f}%", end="", file=sys.stderr)
    except BrokenPipeError:
        pass
    finally:
        video.close()
        if cancelled:
            enc.kill()
            enc.wait()
        else:
            enc.stdin.close()
            code = enc.wait()
    if cancelled:
        output.unlink(missing_ok=True)
        raise RenderCancelled("render cancelled")
    if verbose:
        print(f"\r  rendered {written} frames" + " " * 20, file=sys.stderr)
    if code != 0:
        output.unlink(missing_ok=True)
        raise RenderError(f"ffmpeg failed with exit code {code}")
    if progress_cb:
        progress_cb(1.0)
    return output


def render_still(project: Project, seg: Segment, frame: Optional[np.ndarray] = None) -> np.ndarray:
    """One fully-lit frame for quick previews (dark gradient background if no frame given)."""
    if frame is None:
        g = np.linspace(40, 10, CANVAS_H, dtype=np.float32)[:, None, None]
        canvas = np.broadcast_to(g, (CANVAS_H, CANVAS_W, 3)).astype(np.uint8).copy()
    else:
        canvas = fit_frame(frame, project.fit)
    composite(canvas, build_sprites(project, seg), glow=1.0, opacity=1.0)
    return canvas
