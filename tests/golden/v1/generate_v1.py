"""Regenerate v1 reference frames. MUST be run from a checkout of v0.1.x code (main @ 6e23914):
    git worktree add /tmp/v1 6e23914 && cd /tmp/v1 && PYTHONPATH=. python <repo>/tests/golden/v1/generate_v1.py <repo>/tests/golden/v1
Uses only the v0.1 API (load_job, build_overlay, composite, envelope, fit_frame)."""
import json, sys
from pathlib import Path
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from synthetic import synthetic_frame  # noqa: E402
from musclereels.exercises import ExerciseDB
from musclereels.overlay import build_overlay, composite
from musclereels.project import Job, load_job, make_segment
from musclereels.render import envelope, fit_frame

CASES = json.loads((Path(__file__).parent / "cases.json").read_text())
out = Path(sys.argv[1])


def job_for(case):
    if case["kind"] == "script":
        return load_job(Path(__file__).resolve().parents[3] / case["script"])
    db = ExerciseDB()
    seg = make_segment({"exercise": case["exercise"], "start": 0, "end": None, "subtitle": case.get("subtitle")}, db)
    return Job(input=Path("x.mp4"), output=Path("y.mp4"), segments=[seg], position=case["position"])


for case in CASES:
    job = job_for(case)
    cache = {}
    for t in case["times"]:
        frame = fit_frame(synthetic_frame(t, tuple(case["source_size"])), job.fit)
        for i, seg in enumerate(job.segments):
            if seg.start <= t < seg.end:
                if i not in cache:
                    cache[i] = build_overlay(seg.title, seg.subtitle, seg.primary, seg.secondary,
                                             job.theme, job.position, job.card_scale)
                glow, op = envelope(t, seg, job.pulse_hz)
                composite(frame, cache[i], glow, op)
        cv2.imwrite(str(out / f"{case['name']}_t{t:.2f}.png"), frame)
print("ok")
