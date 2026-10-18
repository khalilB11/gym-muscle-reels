"""Animated stand-in athlete for demo reels: a simple 2D rig driven by joint angles.

    from tools.demo_athlete import make_clip, PATTERN_OF
    make_clip("squat", "demo/clips/squat.mp4")

Each movement pattern is a function phase(0..1) -> (joints, props). Side view faces right (+x);
angles are degrees from straight down (limbs) or from upright (torso), positive = forward.
This is demo material only: it shows the movement, not perfect biomechanics.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

W, H, FPS = 720, 1280, 30
FLOOR = 1180
K = 0.85
L = dict(shin=125, thigh=135, torso=168, upper=100, fore=95, head=26, neck=14)

SKIN, SKIN_FAR = (150, 170, 205), (112, 128, 156)
SHIRT, SHORTS = (60, 60, 200), (55, 50, 45)
SHORTS_FAR, SHOE = (40, 36, 33), (28, 28, 30)
METAL, PLATE, PAD, FRAME = (175, 178, 185), (28, 28, 32), (40, 44, 52), (70, 74, 82)


def v(angle_deg: float, length: float) -> np.ndarray:
    a = math.radians(angle_deg)
    return np.array([math.sin(a), math.cos(a)]) * length


def up(angle_deg: float, length: float) -> np.ndarray:          # torso: 0 = upright, + = lean forward
    a = math.radians(angle_deg)
    return np.array([math.sin(a), -math.cos(a)]) * length


def ease(t: float, period: float = 2.4) -> float:
    return (1 - math.cos(2 * math.pi * t / period)) / 2


def lerp(a, b, p):
    return a + (b - a) * p


# --- side-view skeleton ------------------------------------------------------------------

def side_body(hip, torso, thigh, shin, upper, fore, thigh2=None, shin2=None, upper2=None, fore2=None, foot=0.0):
    """Joints for a side-view body from absolute segment angles. *2 = far-side limbs (default = same)."""
    hip = np.asarray(hip, float)
    j = {"hip": hip}
    j["shoulder"] = hip + up(torso, L["torso"])
    j["neck"] = j["shoulder"] + up(torso * 0.6, L["neck"])
    j["head"] = j["neck"] + up(torso * 0.6, L["head"] + 4) + np.array([4, 0])
    for side, (th, sh, ua, fa) in (("near", (thigh, shin, upper, fore)),
                                   ("far", (thigh2 if thigh2 is not None else thigh, shin2 if shin2 is not None else shin,
                                            upper2 if upper2 is not None else upper, fore2 if fore2 is not None else fore))):
        knee = hip + v(th, L["thigh"])
        ankle = knee + v(sh, L["shin"])
        elbow = j["shoulder"] + v(ua, L["upper"])
        wrist = elbow + v(fa, L["fore"])
        j[f"knee_{side}"], j[f"ankle_{side}"], j[f"elbow_{side}"], j[f"wrist_{side}"] = knee, ankle, elbow, wrist
        j[f"toe_{side}"] = ankle + v(90 + foot, 30)
    return j


def arm_ik(shoulder, target, elbow_down: bool = True) -> tuple[float, float]:
    """(upper, fore) angles that put the wrist on `target` (two-bone IK)."""
    d = np.asarray(target, float) - np.asarray(shoulder, float)
    dist = min(max(np.linalg.norm(d), 1e-3), L["upper"] + L["fore"] - 1)
    a = math.acos(max(-1, min(1, (L["upper"] ** 2 + dist ** 2 - L["fore"] ** 2) / (2 * L["upper"] * dist))))
    base = math.degrees(math.atan2(d[0], d[1]))
    upper = base + (math.degrees(a) if elbow_down else -math.degrees(a))
    elbow = np.asarray(shoulder, float) + v(upper, L["upper"])
    fore = math.degrees(math.atan2(*(np.asarray(target, float) - elbow)))
    return upper, fore


def anchored(ankle, torso, thigh, shin, upper, fore, **kw):
    """Side body placed so the near ankle sits on `ankle` (feet on the floor)."""
    ankle = np.asarray(ankle, float)
    hip = ankle - v(thigh, L["thigh"]) - v(shin, L["shin"])
    return side_body(hip, torso, thigh, shin, upper, fore, **kw)


def draw_side(img, j, props_back=(), props_front=()):
    def line(a, b, col, w):
        cv2.line(img, tuple(np.round(a).astype(int)), tuple(np.round(b).astype(int)), col, int(w * K), cv2.LINE_AA)

    for p in props_back:
        p(img)
    line(j["shoulder"], j["elbow_far"], SKIN_FAR, 26)
    line(j["elbow_far"], j["wrist_far"], SKIN_FAR, 22)
    line(j["hip"], j["knee_far"], SHORTS_FAR, 48)
    line(j["knee_far"], j["ankle_far"], SKIN_FAR, 34)
    line(j["ankle_far"], j["toe_far"], SHOE, 20)
    line(j["hip"], j["shoulder"], SHIRT, 62)
    line(j["shoulder"], j["neck"], SKIN, 22)
    cv2.circle(img, tuple(np.round(j["head"]).astype(int)), int(L["head"] * K * 1.25), SKIN, -1, cv2.LINE_AA)
    line(j["hip"], j["knee_near"], SHORTS, 50)
    line(j["knee_near"], j["ankle_near"], SKIN, 36)
    line(j["ankle_near"], j["toe_near"], SHOE, 22)
    line(j["shoulder"], j["elbow_near"], SKIN, 28)
    line(j["elbow_near"], j["wrist_near"], SKIN, 24)
    for p in props_front:
        p(img)


# --- front-view skeleton -------------------------------------------------------------------

def draw_front(img, cx, floor, arm_abd, shrug=0.0, leg_abd=6.0, elbow_bend=10.0, hold=None):
    """Standing front view. arm_abd: degrees out to the side; leg_abd: legs apart."""
    hip_y = floor - (L["thigh"] + L["shin"]) * math.cos(math.radians(leg_abd))
    sh_y = hip_y - L["torso"] - shrug
    hip_w, sh_w = 34 * K, 52 * K

    def line(a, b, col, w):
        cv2.line(img, tuple(np.round(a).astype(int)), tuple(np.round(b).astype(int)), col, int(w * K), cv2.LINE_AA)

    for s in (-1, 1):
        hip = np.array([cx + s * hip_w * 0.6, hip_y])
        knee = hip + np.array([s * math.sin(math.radians(leg_abd)), math.cos(math.radians(leg_abd))]) * L["thigh"]
        ankle = knee + np.array([s * math.sin(math.radians(leg_abd)), math.cos(math.radians(leg_abd))]) * L["shin"]
        line(hip, knee, SHORTS, 50)
        line(knee, ankle, SKIN, 36)
        line(ankle, ankle + np.array([s * 18, 4]), SHOE, 22)
    pts = np.array([[cx - sh_w, sh_y], [cx + sh_w, sh_y], [cx + hip_w, hip_y + 10], [cx - hip_w, hip_y + 10]], np.int32)
    cv2.fillPoly(img, [pts], SHIRT, cv2.LINE_AA)
    line((cx, sh_y), (cx, sh_y - 24 * K + shrug * 0.3), SKIN, 22)
    cv2.circle(img, (int(cx), int(sh_y - 52 * K + shrug * 0.3)), int(L["head"] * K * 1.25), SKIN, -1, cv2.LINE_AA)
    for s in (-1, 1):
        sh = np.array([cx + s * sh_w, sh_y + 8])
        a = math.radians(arm_abd)
        elbow = sh + np.array([s * math.sin(a), math.cos(a)]) * L["upper"]
        a2 = math.radians(arm_abd + elbow_bend)
        wrist = elbow + np.array([s * math.sin(a2), math.cos(a2)]) * L["fore"]
        line(sh, elbow, SKIN, 28)
        line(elbow, wrist, SKIN, 24)
        if hold == "dumbbell":
            dumbbell(img, wrist, vertical=False)
    return img


# --- props ---------------------------------------------------------------------------------

def barbell(img, c, half=170):
    c = np.round(c).astype(int)
    cv2.line(img, (c[0] - half, c[1]), (c[0] + half, c[1]), METAL, 9, cv2.LINE_AA)
    for dx in (-half + 30, half - 30):
        cv2.ellipse(img, (c[0] + dx, c[1]), (14, 58), 0, 0, 360, PLATE, -1, cv2.LINE_AA)
        cv2.ellipse(img, (c[0] + dx, c[1]), (14, 58), 0, 0, 360, (80, 80, 90), 2, cv2.LINE_AA)


def barbell_side(img, c):            # bar seen end-on (side view)
    c = np.round(c).astype(int)
    cv2.circle(img, tuple(c), 46, PLATE, -1, cv2.LINE_AA)
    cv2.circle(img, tuple(c), 46, (80, 80, 90), 3, cv2.LINE_AA)
    cv2.circle(img, tuple(c), 8, METAL, -1, cv2.LINE_AA)


def dumbbell(img, c, vertical=True):
    c = np.round(c).astype(int)
    d = np.array([0, 18]) if vertical else np.array([18, 0])
    cv2.line(img, tuple(c - d), tuple(c + d), METAL, 6, cv2.LINE_AA)
    for e in (c - d, c + d):
        cv2.circle(img, tuple(e), 13, PLATE, -1, cv2.LINE_AA)


def kettlebell(img, c):
    c = np.round(c).astype(int)
    cv2.circle(img, (c[0], c[1] + 26), 26, PLATE, -1, cv2.LINE_AA)
    cv2.ellipse(img, (c[0], c[1] + 4), (14, 14), 0, 180, 360, METAL, 5, cv2.LINE_AA)


def rect(img, x0, y0, x1, y1, col=PAD):
    cv2.rectangle(img, (int(x0), int(y0)), (int(x1), int(y1)), col, -1, cv2.LINE_AA)


def cable(img, a, b):
    cv2.line(img, tuple(np.round(a).astype(int)), tuple(np.round(b).astype(int)), (150, 150, 160), 2, cv2.LINE_AA)


def background():
    bg = np.zeros((H, W, 3), np.uint8)
    for y in range(H):
        val = 36 + int(26 * y / H)
        bg[y] = (val + 6, val + 2, val)
    rect(bg, 0, FLOOR + 18, W, H, (34, 36, 40))
    cv2.line(bg, (0, FLOOR + 18), (W, FLOOR + 18), (70, 74, 82), 3)
    return bg


# --- movement patterns -------------------------------------------------------------------------
# Each returns a frame-drawing function of time t (seconds).

def squat(t):
    p = ease(t) ** 1.2
    torso = lerp(10, 42, p)
    j = anchored((330, FLOOR), torso, lerp(8, 82, p), lerp(-2, -32, p), 0, 0)
    bar = j["shoulder"] + np.array([-10, -12])
    hand = bar + np.array([-4, 4])
    upper, fore = arm_ik(j["shoulder"], hand, elbow_down=True)
    j = anchored((330, FLOOR), torso, lerp(8, 82, p), lerp(-2, -32, p), upper, fore)
    return j, [lambda im: barbell_side(im, bar)], []


def front_squat(t):
    p = ease(t) ** 1.2
    torso = lerp(4, 22, p)
    j = anchored((330, FLOOR), torso, lerp(8, 88, p), lerp(-2, -36, p), 0, 0)
    bar = j["shoulder"] + up(torso, 6) + np.array([34, 0])
    upper, fore = arm_ik(j["shoulder"], bar + np.array([-6, 6]), elbow_down=True)
    j = anchored((330, FLOOR), torso, lerp(8, 88, p), lerp(-2, -36, p), upper, fore)
    return j, [lambda im: barbell_side(im, bar)], []


def hinge(t, knee=18, bell="barbell", swing=False):
    p = ease(t)
    torso = lerp(4, 82, p)
    thigh = lerp(4, knee + 6, p)
    j = anchored((330, FLOOR), torso, thigh, lerp(0, -12, p), lerp(0, 0, p) if not swing else lerp(90, 0, p), 0)
    if swing:
        j = anchored((330, FLOOR), torso, thigh, lerp(0, -12, p), lerp(95, -15, p), lerp(95, -15, p))
    hand = j["wrist_near"]
    if bell == "barbell":
        return j, [], [lambda im: barbell_side(im, hand + np.array([0, 20]))]
    if bell == "kettlebell":
        return j, [], [lambda im: kettlebell(im, hand)]
    return j, [], []


def lunge(t, rear_foot_on_bench=False):
    p = ease(t)
    front_ankle = np.array([420, FLOOR])
    thigh_f, shin_f = lerp(30, 85, p), lerp(-6, -12, p)
    hip = front_ankle - v(thigh_f, L["thigh"]) - v(shin_f, L["shin"])
    if rear_foot_on_bench:
        rear = np.array([150, FLOOR - 120])
    else:
        rear = np.array([180, FLOOR])
    d = rear - hip
    dist = min(np.linalg.norm(d), L["thigh"] + L["shin"] - 1)
    # two-bone IK for the rear leg (knee pointing down/forward)
    a = math.acos((L["thigh"] ** 2 + dist ** 2 - L["shin"] ** 2) / (2 * L["thigh"] * dist))
    base = math.atan2(d[0], d[1])
    thigh_r = math.degrees(base + a)
    knee_r = hip + v(thigh_r, L["thigh"])
    shin_r = math.degrees(math.atan2(*(rear - knee_r)))
    j = side_body(hip, 6, thigh_f, shin_f, 4, 4, thigh2=thigh_r, shin2=shin_r)
    props = [lambda im: rect(im, 90, FLOOR - 110, 230, FLOOR - 92)] if rear_foot_on_bench else []
    return j, props, [lambda im: dumbbell(im, j["wrist_near"])]


def bench(t, incline=0.0, motion="press"):
    p = ease(t)
    bench_y = FLOOR - 150
    hip = np.array([420, bench_y - 28])
    torso = -90 + incline          # lying: torso points to -x (head left); incline raises the head
    if motion == "press":
        upper = lerp(178, 128, p) + incline * 0.5
        fore = lerp(180, 205, p) + incline * 0.5
    elif motion == "fly":
        upper = lerp(178, 110, p) + incline * 0.5
        fore = upper + 12
    else:                           # skull crusher: upper arm fixed, forearm hinges
        upper = 165
        fore = lerp(170, 300, p)
    j = side_body(hip, torso, 72, 0, upper, fore)
    props_back = [lambda im: rect(im, 150, bench_y - 6, 520, bench_y + 10, PAD),
                  lambda im: rect(im, 190, bench_y + 10, 210, FLOOR + 18, FRAME),
                  lambda im: rect(im, 460, bench_y + 10, 480, FLOOR + 18, FRAME)]
    if incline:
        props_back.append(lambda im: cv2.line(im, (420, bench_y), (190, bench_y - int(230 * math.sin(math.radians(incline)))),
                                              PAD, 22, cv2.LINE_AA))
    hold = (lambda im: barbell_side(im, j["wrist_near"])) if motion != "fly" else (lambda im: dumbbell(im, j["wrist_near"]))
    return j, props_back, [hold]


def push_up(t):
    p = ease(t)
    feet = np.array([560, FLOOR])
    tilt = lerp(-70, -80, p)                  # body angle from vertical, head to -x
    hip = feet + np.array([math.sin(math.radians(tilt)), -math.cos(math.radians(tilt))]) * (L["thigh"] + L["shin"])
    shoulder = hip + np.array([math.sin(math.radians(tilt)), -math.cos(math.radians(tilt))]) * L["torso"]
    hand = np.array([shoulder[0] + 6, FLOOR - 4])
    d = hand - shoulder
    dist = min(np.linalg.norm(d), L["upper"] + L["fore"] - 1)
    a = math.acos((L["upper"] ** 2 + dist ** 2 - L["fore"] ** 2) / (2 * L["upper"] * dist))
    base = math.atan2(d[0], d[1])
    upper = math.degrees(base - a)
    elbow = shoulder + v(upper, L["upper"])
    fore = math.degrees(math.atan2(*(hand - elbow)))
    leg_ang = math.degrees(math.atan2(*(feet - hip)))
    j = side_body(hip, tilt, leg_ang, leg_ang, upper, fore)
    return j, [], []


def dips(t):
    p = ease(t)
    bar_y = FLOOR - 470
    hand = np.array([360, bar_y])
    shoulder = hand + np.array([-6, lerp(-150, -60, p)])
    d = hand - shoulder
    dist = min(np.linalg.norm(d), L["upper"] + L["fore"] - 1)
    a = math.acos(max(-1, min(1, (L["upper"] ** 2 + dist ** 2 - L["fore"] ** 2) / (2 * L["upper"] * dist))))
    upper = math.degrees(math.atan2(d[0], d[1]) - a)
    elbow = shoulder + v(upper, L["upper"])
    fore = math.degrees(math.atan2(*(hand - elbow)))
    torso = 12
    hip = shoulder - up(torso, L["torso"])
    j = side_body(hip, torso, 20, -70, upper, fore)
    props = [lambda im: rect(im, 250, bar_y - 6, 470, bar_y + 8, METAL),
             lambda im: rect(im, 250, bar_y + 8, 266, FLOOR + 18, FRAME),
             lambda im: rect(im, 454, bar_y + 8, 470, FLOOR + 18, FRAME)]
    return j, props, []


def overhead_press(t):
    p = ease(t)
    j = anchored((330, FLOOR), 0, 2, -2, lerp(35, 178, p), lerp(168, 180, p))
    return j, [], [lambda im: barbell_side(im, j["wrist_near"])]


def pull_up(t, seated=False):
    p = ease(t)
    bar_y = 560 if not seated else 640
    hand = np.array([380, bar_y])
    shoulder = hand + np.array([-18, lerp(L["upper"] + L["fore"] - 6, 70, p)])
    d = hand - shoulder
    dist = min(np.linalg.norm(d), L["upper"] + L["fore"] - 1)
    a = math.acos(max(-1, min(1, (L["upper"] ** 2 + dist ** 2 - L["fore"] ** 2) / (2 * L["upper"] * dist))))
    upper = math.degrees(math.atan2(d[0], d[1]) - a) % 360
    elbow = shoulder + v(upper, L["upper"])
    fore = math.degrees(math.atan2(*(hand - elbow)))
    torso = -8
    hip = shoulder - up(torso, L["torso"])
    if seated:
        hip = np.array([330, FLOOR - 150])
        shoulder = hip + up(-12, L["torso"])
        d = hand - shoulder
        dist = min(np.linalg.norm(d), L["upper"] + L["fore"] - 1)
        a = math.acos(max(-1, min(1, (L["upper"] ** 2 + dist ** 2 - L["fore"] ** 2) / (2 * L["upper"] * dist))))
        upper = math.degrees(math.atan2(d[0], d[1]) - a) % 360
        elbow = shoulder + v(upper, L["upper"])
        fore = math.degrees(math.atan2(*(hand - elbow)))
        j = side_body(hip, -12, 90, 0, upper, fore)
        props = [lambda im: rect(im, 250, FLOOR - 140, 420, FLOOR - 120),
                 lambda im: rect(im, 320, FLOOR - 120, 340, FLOOR + 18, FRAME),
                 lambda im: rect(im, 260, bar_y - 6, 520, bar_y + 6, METAL),
                 lambda im: cable(im, (390, bar_y), (390, 120))]
        return j, props, []
    j = side_body(hip, torso, 25, -60, upper, fore)
    props = [lambda im: rect(im, 200, bar_y - 6, 560, bar_y + 6, METAL),
             lambda im: rect(im, 200, bar_y + 6, 214, FLOOR + 18, FRAME)]
    return j, props, []


def row(t, kind="barbell"):
    p = ease(t)
    if kind == "barbell":
        j = anchored((330, FLOOR), 68, 22, -10, lerp(0, -38, p), lerp(0, 40, p))
        return j, [], [lambda im: barbell_side(im, j["wrist_near"] + np.array([0, 16]))]
    if kind == "cable":                         # seated cable row
        hip = np.array([260, FLOOR - 70])
        j = side_body(hip, lerp(18, -4, p), 78, 20, lerp(88, 25, p), lerp(90, 92, p))
        props = [lambda im: rect(im, 170, FLOOR - 50, 330, FLOOR - 30),
                 lambda im: rect(im, 560, FLOOR - 160, 600, FLOOR + 18, FRAME),
                 lambda im: cable(im, j["wrist_near"], (560, FLOOR - 130))]
        return j, props, []
    # face pull: standing, rope pulled to the face from a high cable
    j = anchored((300, FLOOR), -4, 0, 0, lerp(100, 115, p), lerp(100, 300, p) % 360)
    props = [lambda im: rect(im, 600, 300, 630, FLOOR + 18, FRAME),
             lambda im: cable(im, j["wrist_near"], (600, 520))]
    return j, props, []


def curl(t):
    p = ease(t)
    j = anchored((330, FLOOR), 0, 0, 0, 4, lerp(4, 150, p))
    return j, [], [lambda im: dumbbell(im, j["wrist_near"], vertical=False)]


def pushdown(t):
    p = ease(t)
    j = anchored((300, FLOOR), 8, 2, -2, 18, lerp(105, 10, p))
    props = [lambda im: rect(im, 520, 300, 550, FLOOR + 18, FRAME),
             lambda im: cable(im, j["wrist_near"], (520, 360))]
    return j, props, []


def calf_raise(t):
    p = ease(t, 1.8)
    lift = lerp(0, 34, p)
    j = anchored((330, FLOOR - lift), 0, 0, 0, 0, 0, foot=lerp(0, 55, p))
    return j, [lambda im: rect(im, 300, FLOOR - 6, 420, FLOOR + 18, FRAME)], [lambda im: dumbbell(im, j["wrist_near"])]


def leg_machine(t, kind="extension"):
    p = ease(t)
    if kind == "extension":
        hip = np.array([300, FLOOR - 230])
        j = side_body(hip, -6, 90, lerp(0, 82, p), 20, 60)
        props = [lambda im: rect(im, 210, FLOOR - 212, 330, FLOOR - 190),
                 lambda im: rect(im, 200, FLOOR - 420, 225, FLOOR - 190),
                 lambda im: rect(im, 250, FLOOR - 190, 270, FLOOR + 18, FRAME)]
        return j, props, []
    # lying leg curl: prone, shin swings up
    hip = np.array([380, FLOOR - 200])
    j = side_body(hip, -90, 90, lerp(90, 195, p), -80, -90)
    props = [lambda im: rect(im, 120, FLOOR - 176, 600, FLOOR - 160),
             lambda im: rect(im, 300, FLOOR - 160, 320, FLOOR + 18, FRAME)]
    return j, props, []


def hip_thrust(t):
    p = ease(t)
    bench_y = FLOOR - 170
    shoulder = np.array([230, bench_y - 20])
    torso_ang = lerp(-125, -92, p)            # pivot around the shoulders on the bench
    hip = shoulder - up(torso_ang, L["torso"])
    feet = np.array([520, FLOOR])
    d = feet - hip
    dist = min(np.linalg.norm(d), L["thigh"] + L["shin"] - 1)
    a = math.acos((L["thigh"] ** 2 + dist ** 2 - L["shin"] ** 2) / (2 * L["thigh"] * dist))
    thigh = math.degrees(math.atan2(d[0], d[1]) + a)
    knee = hip + v(thigh, L["thigh"])
    shin = math.degrees(math.atan2(*(feet - knee)))
    j = side_body(hip, torso_ang, thigh, shin, 170, 160)
    props = [lambda im: rect(im, 110, bench_y, 250, bench_y + 22),
             lambda im: rect(im, 170, bench_y + 22, 190, FLOOR + 18, FRAME)]
    return j, props, [lambda im: barbell_side(im, hip + np.array([0, -30]))]


def core(t, kind="plank"):
    p = ease(t)
    if kind == "plank":
        feet = np.array([560, FLOOR])
        tilt = -77 + 1.5 * math.sin(t * 2)
        hip = feet + np.array([math.sin(math.radians(tilt)), -math.cos(math.radians(tilt))]) * (L["thigh"] + L["shin"])
        leg = math.degrees(math.atan2(*(feet - hip)))
        j = side_body(hip, tilt, leg, leg, 0, -90)
        return j, [], []
    if kind == "crunch":
        hip = np.array([400, FLOOR - 30])
        j = side_body(hip, lerp(-86, -50, p), 140, 25, lerp(150, 115, p), lerp(150, 112, p))
        return j, [], []
    if kind == "leg_raise":
        bar_y = 560
        hand = np.array([360, bar_y])
        shoulder = hand + np.array([-6, L["upper"] + L["fore"] - 4])
        hip = shoulder - up(lerp(0, -12, p), L["torso"])
        j = side_body(hip, lerp(0, -12, p), lerp(4, 92, p), lerp(4, 92, p), 180, 180)
        props = [lambda im: rect(im, 200, bar_y - 6, 560, bar_y + 6, METAL),
                 lambda im: rect(im, 200, bar_y + 6, 214, FLOOR + 18, FRAME)]
        return j, props, []
    # russian twist: seated V, hands swing
    hip = np.array([360, FLOOR - 26])
    swing = math.sin(2 * math.pi * t / 1.6)
    j = side_body(hip, -38, 115, 60, lerp(60, 110, (swing + 1) / 2), lerp(80, 140, (swing + 1) / 2))
    return j, [], [lambda im: kettlebell(im, j["wrist_near"] + np.array([0, -18]))]


PATTERNS = {
    "squat": squat, "front_squat": front_squat,
    "hinge": lambda t: hinge(t), "rdl": lambda t: hinge(t, knee=8), "swing": lambda t: hinge(t, bell="kettlebell", swing=True),
    "lunge": lambda t: lunge(t), "split_squat": lambda t: lunge(t, rear_foot_on_bench=True),
    "bench": lambda t: bench(t), "incline": lambda t: bench(t, incline=30), "fly": lambda t: bench(t, motion="fly"),
    "skull_crusher": lambda t: bench(t, motion="skull"),
    "push_up": push_up, "dips": dips, "overhead_press": overhead_press,
    "pull_up": lambda t: pull_up(t), "pulldown": lambda t: pull_up(t, seated=True),
    "row": lambda t: row(t), "cable_row": lambda t: row(t, "cable"), "face_pull": lambda t: row(t, "face"),
    "curl": curl, "pushdown": pushdown, "calf_raise": calf_raise,
    "leg_extension": lambda t: leg_machine(t), "leg_curl": lambda t: leg_machine(t, "curl"),
    "hip_thrust": hip_thrust,
    "plank": lambda t: core(t), "crunch": lambda t: core(t, "crunch"), "leg_raise": lambda t: core(t, "leg_raise"),
    "twist": lambda t: core(t, "twist"),
}
FRONT_PATTERNS = {
    "lateral_raise": lambda t: dict(arm_abd=lerp(12, 88, ease(t)), hold="dumbbell"),
    "rear_fly": lambda t: dict(arm_abd=lerp(18, 80, ease(t)), elbow_bend=20, hold="dumbbell"),
    "shrug": lambda t: dict(arm_abd=8, shrug=lerp(0, 26, ease(t, 1.6)), hold="dumbbell"),
    "adductor": lambda t: dict(arm_abd=14, leg_abd=lerp(22, 4, ease(t))),
}

PATTERN_OF = {
    "bench_press": "bench", "incline_bench_press": "incline", "dumbbell_fly": "fly", "cable_crossover": "fly",
    "push_up": "push_up", "dips": "dips", "overhead_press": "overhead_press", "lateral_raise": "lateral_raise",
    "rear_delt_fly": "rear_fly", "face_pull": "face_pull", "shrug": "shrug", "pull_up": "pull_up",
    "lat_pulldown": "pulldown", "barbell_row": "row", "seated_cable_row": "cable_row", "deadlift": "hinge",
    "romanian_deadlift": "rdl", "squat": "squat", "front_squat": "front_squat", "leg_press": "squat",
    "lunge": "lunge", "bulgarian_split_squat": "split_squat", "hip_thrust": "hip_thrust",
    "leg_extension": "leg_extension", "leg_curl": "leg_curl", "adductor_machine": "adductor",
    "calf_raise": "calf_raise", "kettlebell_swing": "swing", "biceps_curl": "curl", "hammer_curl": "curl",
    "triceps_pushdown": "pushdown", "skull_crusher": "skull_crusher", "plank": "plank", "crunch": "crunch",
    "hanging_leg_raise": "leg_raise", "russian_twist": "twist",
}


def render_frame(pattern: str, t: float, bg=None) -> np.ndarray:
    img = (bg if bg is not None else background()).copy()
    if pattern in FRONT_PATTERNS:
        draw_front(img, W / 2, FLOOR, **FRONT_PATTERNS[pattern](t))
        return img
    j, back, front = PATTERNS[pattern](t)
    draw_side(img, j, back, front)
    return img


def make_clip(pattern: str, path, secs: float = 8.0) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    bg = background()
    for i in range(int(FPS * secs)):
        out.write(render_frame(pattern, i / FPS, bg))
    out.release()
    return path


if __name__ == "__main__":
    import sys
    make_clip(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else f"demo/clips/{sys.argv[1]}.mp4")
