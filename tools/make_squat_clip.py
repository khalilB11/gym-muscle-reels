"""Synthetic 'athlete squatting' clip (side view): a stand-in for real gym footage in demos.

    python tools/make_squat_clip.py [demo/squat_clip.mp4]
"""
import math
import sys
from pathlib import Path
import cv2
import numpy as np

W, H, FPS, SECS = 720, 1280, 30, 12
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "demo/squat_clip.mp4")
OUT.parent.mkdir(parents=True, exist_ok=True)
out = cv2.VideoWriter(str(OUT), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))

# static background: dark gym wall + floor + rack
bg = np.zeros((H, W, 3), np.uint8)
for y in range(H):
    v = 38 + int(28 * y / H)
    bg[y] = (v + 6, v + 2, v)
cv2.rectangle(bg, (0, 1105), (W, H), (34, 36, 40), -1)
cv2.line(bg, (0, 1105), (W, 1105), (70, 74, 82), 3)
for x in (60, 420):
    cv2.rectangle(bg, (x - 8, 640), (x + 10, 1105), (58, 62, 70), -1)
for y in range(700, 1080, 60):
    for x in (60, 420):
        cv2.circle(bg, (x, y), 5, (90, 95, 105), -1)

K = 0.72
L_SHIN, L_THIGH, L_TORSO = 245 * K, 245 * K, 300 * K
ANKLE = np.array([235.0, 1085.0])
SKIN, SHIRT, SHORTS = (150, 170, 205), (60, 60, 200), (55, 50, 45)


def knee_from(hip):
    # knee in front of the hip/ankle line (circle intersection)
    d = np.linalg.norm(hip - ANKLE)
    d = min(d, L_SHIN + L_THIGH - 1)
    a = d / 2
    h = math.sqrt(max(L_SHIN ** 2 - a ** 2, 0))
    mid = ANKLE + (hip - ANKLE) * (a / d)
    perp = np.array([-(hip - ANKLE)[1], (hip - ANKLE)[0]]) / d
    k1, k2 = mid + perp * h, mid - perp * h
    return k1 if k1[0] > k2[0] else k2


def pt(p):
    return int(round(p[0])), int(round(p[1]))


for i in range(FPS * SECS):
    t = i / FPS
    depth = (1 - math.cos(2 * math.pi * t / 2.4)) / 2          # one rep every 2.4 s
    depth = depth ** 1.2
    hip = ANKLE + np.array([-95 * depth * K, (-470 + 250 * depth) * K])
    knee = knee_from(hip)
    lean = math.radians(8 + 38 * depth)
    shoulder = hip + np.array([math.sin(lean), -math.cos(lean)]) * L_TORSO
    head = shoulder + np.array([math.sin(lean) * 20 + 18, -70]) * K
    img = bg.copy()
    cv2.line(img, pt(ANKLE), pt(knee), SKIN, 34, cv2.LINE_AA)
    cv2.line(img, pt(knee), pt(hip), SHORTS, 46, cv2.LINE_AA)
    cv2.line(img, pt(hip), pt(shoulder), SHIRT, 56, cv2.LINE_AA)
    cv2.ellipse(img, pt(ANKLE + [20, 16]), (38, 12), 0, 0, 360, (30, 30, 30), -1, cv2.LINE_AA)
    elbow = shoulder + np.array([-40, 25])
    cv2.line(img, pt(shoulder), pt(elbow), SKIN, 22, cv2.LINE_AA)
    cv2.line(img, pt(elbow), pt(shoulder + [-13, -13]), SKIN, 19, cv2.LINE_AA)
    cv2.circle(img, pt(head), 32, SKIN, -1, cv2.LINE_AA)
    bar = shoulder + np.array([-9, -16])
    cv2.line(img, pt(bar + [-190, 0]), pt(bar + [190, 0]), (175, 178, 185), 12, cv2.LINE_AA)
    for dx in (-155, 155):
        cv2.ellipse(img, pt(bar + [dx, 0]), (16, 66), 0, 0, 360, (25, 25, 28), -1, cv2.LINE_AA)
        cv2.ellipse(img, pt(bar + [dx, 0]), (16, 66), 0, 0, 360, (80, 80, 90), 3, cv2.LINE_AA)
    out.write(img)
out.release()
print(f"✓ Saved {OUT}")
