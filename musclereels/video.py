"""Reading source clips: probing, exact frame access, VFR proxies and 9:16 reframing.

The app preview and the export both read frames through VideoSource so they see the same pixels.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional

import cv2
import numpy as np

CACHE_DIR = ".musclereels-cache"


class VideoError(RuntimeError):
    pass


def ffmpeg_exe() -> Optional[str]:
    """System ffmpeg first, then the one bundled with imageio-ffmpeg (app extra)."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def ffprobe_exe() -> Optional[str]:
    exe = shutil.which("ffprobe")
    if exe:
        return exe
    ff = ffmpeg_exe()
    if ff:
        cand = Path(ff).with_name("ffprobe" + Path(ff).suffix)
        if cand.exists():
            return str(cand)
    return None


@dataclass(frozen=True)
class VideoInfo:
    duration: float
    fps: float
    size: tuple[int, int]          # width, height as displayed
    frame_count: int
    has_audio: bool
    needs_proxy: bool


def _rate(s: str) -> float:
    try:
        n, d = s.split("/")
        return float(n) / float(d) if float(d) else 0.0
    except (ValueError, AttributeError):
        return 0.0


def _probe_ffprobe(path: Path, exe: str) -> Optional[dict]:
    r = subprocess.run([exe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return json.loads(r.stdout or "{}")


def _probe_ffmpeg_text(path: Path) -> dict:
    """Fallback when ffprobe is missing: parse `ffmpeg -i` output (assumes constant frame rate)."""
    ff = ffmpeg_exe()
    if not ff:
        return {}
    r = subprocess.run([ff, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    text = r.stderr
    info: dict = {"has_audio": bool(re.search(r"Stream #\S+.*Audio:", text))}
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", text)
    if m:
        info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return info


def probe(path: str | Path) -> VideoInfo:
    path = Path(path)
    if not path.exists():
        raise VideoError(f"Video not found: {path}")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VideoError(f"Could not open video (unsupported or damaged file): {path}")
    ok, frame = cap.read()
    cv_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cv_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    if not ok:
        raise VideoError(f"No video frames could be read from {path}")
    h, w = frame.shape[:2]

    fps, duration, has_audio, needs_proxy, count = cv_fps, (cv_count / cv_fps if cv_count else 0.0), False, False, cv_count
    exe = ffprobe_exe()
    data = _probe_ffprobe(path, exe) if exe else None
    if data:
        streams = data.get("streams", [])
        v = next((s for s in streams if s.get("codec_type") == "video"), {})
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        r_rate, avg_rate = _rate(v.get("r_frame_rate", "")), _rate(v.get("avg_frame_rate", ""))
        fps = r_rate or avg_rate or cv_fps
        duration = float(data.get("format", {}).get("duration") or v.get("duration") or duration)
        if r_rate and avg_rate and abs(r_rate - avg_rate) / r_rate > 0.01:
            needs_proxy = True                      # variable frame rate (typical phone footage)
        if v.get("nb_frames", "").isdigit():
            count = int(v["nb_frames"])
    else:
        extra = _probe_ffmpeg_text(path)
        has_audio = extra.get("has_audio", False)
        duration = extra.get("duration", duration)
    if not count:
        count = max(1, round(duration * fps))
    if not duration:
        duration = count / fps
    return VideoInfo(duration=duration, fps=fps, size=(w, h), frame_count=count,
                     has_audio=has_audio, needs_proxy=needs_proxy)


class VideoSource:
    """Exact, seekable frame access. Use one instance per thread."""

    def __init__(self, path: str | Path):
        self.original = Path(path)
        self.path = self.original
        self.info = probe(self.original)
        self._cap: Optional[cv2.VideoCapture] = None
        self._next = -1          # index the capture will return on the next read()

    # -- proxy ------------------------------------------------------------------
    def _proxy_path(self) -> Path:
        st = self.original.stat()
        key = f"{self.original.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode()
        return self.original.parent / CACHE_DIR / f"{self.original.stem}-{hashlib.sha1(key).hexdigest()[:12]}.mp4"

    def prepare(self, progress_cb: Optional[Callable[[float], None]] = None) -> Optional[Path]:
        """Build a constant-frame-rate proxy if the clip needs one.

        Returns the proxy path when it was built now; None when not needed or already cached.
        """
        if not self.info.needs_proxy:
            return None
        proxy = self._proxy_path()
        built = None
        if not proxy.exists():
            ff = ffmpeg_exe()
            if not ff:
                raise VideoError("ffmpeg is required to convert variable-frame-rate clips")
            proxy.parent.mkdir(parents=True, exist_ok=True)
            tmp = proxy.with_suffix(".tmp.mp4")
            fps = self.info.fps
            cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(self.original),
                   "-vf", f"fps={fps:.6f}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "12",
                   "-pix_fmt", "yuv420p", "-progress", "pipe:1", "-nostats", str(tmp)]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
            total_us = max(self.info.duration, 1e-3) * 1e6
            for line in proc.stdout:  # type: ignore[union-attr]
                if line.startswith("out_time_us=") and progress_cb:
                    try:
                        progress_cb(min(0.99, int(line.split("=")[1]) / total_us))
                    except ValueError:
                        pass
            if proc.wait() != 0:
                tmp.unlink(missing_ok=True)
                raise VideoError(f"Could not convert {self.original.name} to constant frame rate")
            os.replace(tmp, proxy)
            built = proxy
        if progress_cb:
            progress_cb(1.0)
        self.path = proxy
        info = probe(proxy)
        self.info = VideoInfo(info.duration, info.fps, info.size, info.frame_count, self.info.has_audio, False)
        self.close()
        return built

    # -- frames -----------------------------------------------------------------
    def _capture(self) -> cv2.VideoCapture:
        if self._cap is None:
            self._cap = cv2.VideoCapture(str(self.path))
            if not self._cap.isOpened():
                raise VideoError(f"Could not open video: {self.path}")
            self._next = 0
        return self._cap

    def index_at(self, t: float) -> int:
        return int(min(max(round(t * self.info.fps), 0), self.info.frame_count - 1))

    def read_index(self, index: int) -> np.ndarray:
        cap = self._capture()
        if index != self._next:
            if 0 < index - self._next <= 30:          # short hop forward: decode through
                while self._next < index:
                    if not cap.grab():
                        break
                    self._next += 1
            else:
                cap.set(cv2.CAP_PROP_POS_FRAMES, index)
                self._next = index
        ok, frame = cap.read()
        if not ok:
            raise VideoError(f"Could not read frame {index} of {self.path.name}")
        self._next = index + 1
        return frame

    def frame_at(self, t: float) -> np.ndarray:
        return self.read_index(self.index_at(t))

    def iter_frames(self, t0: float = 0.0, t1: float = math.inf) -> Iterator[tuple[float, np.ndarray]]:
        """Yield (time, frame) for frames with t0 <= time < t1, decoding sequentially."""
        fps = self.info.fps
        i = max(0, math.ceil(t0 * fps - 1e-6))
        cap = self._capture()
        if self._next != i:
            if 0 < i - self._next <= 30:
                while self._next < i and cap.grab():
                    self._next += 1
            else:
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                self._next = i
        while True:
            t = i / fps
            if t >= t1 - 1e-6:
                break
            ok, frame = cap.read()
            if not ok:
                break
            self._next = i + 1
            yield t, frame
            i += 1

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            self._next = -1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def fit_frame(frame: np.ndarray, mode: str = "auto", out_size: tuple[int, int] = (1080, 1920)) -> np.ndarray:
    """Reframe any clip to out_size (w, h), 9:16 by default.

    cover: fill the screen, cropping the edges (best for vertical clips)
    blur:  whole clip centred over a blurred, zoomed copy (best for landscape)
    """
    W, H = out_size
    h, w = frame.shape[:2]
    if mode == "auto":
        mode = "cover" if w / h <= 0.75 else "blur"

    def resize(img, s):
        nw, nh = max(1, round(img.shape[1] * s)), max(1, round(img.shape[0] * s))
        return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)

    def cover(img, cw, ch):
        r = resize(img, max(cw / img.shape[1], ch / img.shape[0]))
        y, x = (r.shape[0] - ch) // 2, (r.shape[1] - cw) // 2
        return r[y:y + ch, x:x + cw]

    if mode == "cover":
        return np.ascontiguousarray(cover(frame, W, H))

    small = cover(frame, W // 8, H // 8)
    bg = cv2.GaussianBlur(small, (0, 0), 6)
    bg = cv2.resize(bg, (W, H), interpolation=cv2.INTER_LINEAR)
    out = (bg.astype(np.float32) * 0.55).astype(np.uint8)
    fg = resize(frame, min(W / w, H / h))
    y, x = (H - fg.shape[0]) // 2, (W - fg.shape[1]) // 2
    out[y:y + fg.shape[0], x:x + fg.shape[1]] = fg
    return out
