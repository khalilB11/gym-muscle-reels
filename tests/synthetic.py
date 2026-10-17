"""Deterministic test frames that don't depend on any video codec."""
from __future__ import annotations

import numpy as np


def synthetic_frame(t: float, size: tuple[int, int] = (720, 1280)) -> np.ndarray:
    """BGR uint8 frame (width, height = size) whose content changes with t."""
    w, h = size
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    b = (x / w * 200 + 30 * np.sin(t)) % 256
    g = (y / h * 180 + 40 * t) % 256
    r = ((x + y) / (w + h) * 255 + 25 * np.cos(2 * t)) % 256
    frame = np.stack([b, g, r], axis=-1).astype(np.uint8)
    cx, cy = int(w * (0.3 + 0.4 * ((t * 0.37) % 1))), int(h * 0.55)
    yy, xx = np.ogrid[0:h, 0:w]
    frame[(xx - cx) ** 2 + (yy - cy) ** 2 < (min(w, h) // 8) ** 2] = (235, 235, 235)
    return frame
