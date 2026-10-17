"""Compare two videos frame by frame.

    python tools/compare_videos.py a.mp4 b.mp4 [--tolerance 0]

Exit 0 when frame count and size match and every pixel differs by at most --tolerance
(per channel); exit 1 otherwise, reporting the first differing frame.
"""
from __future__ import annotations

import argparse
import sys

import cv2
import numpy as np


def compare(a: str, b: str, tolerance: int = 0) -> tuple[bool, str]:
    ca, cb = cv2.VideoCapture(a), cv2.VideoCapture(b)
    if not ca.isOpened() or not cb.isOpened():
        return False, f"could not open {a if not ca.isOpened() else b}"
    idx, worst = 0, 0
    try:
        while True:
            oka, fa = ca.read()
            okb, fb = cb.read()
            if not oka and not okb:
                return True, f"identical within tolerance {tolerance}: {idx} frames, max diff {worst}"
            if oka != okb:
                return False, f"frame count differs: one video ends at frame {idx}"
            if fa.shape != fb.shape:
                return False, f"frame {idx}: size {fa.shape[1]}x{fa.shape[0]} vs {fb.shape[1]}x{fb.shape[0]}"
            diff = int(np.abs(fa.astype(np.int16) - fb.astype(np.int16)).max())
            worst = max(worst, diff)
            if diff > tolerance:
                return False, f"frame {idx}: max pixel difference {diff} > tolerance {tolerance}"
            idx += 1
    finally:
        ca.release()
        cb.release()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--tolerance", type=int, default=0)
    args = p.parse_args(argv)
    ok, msg = compare(args.a, args.b, args.tolerance)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
