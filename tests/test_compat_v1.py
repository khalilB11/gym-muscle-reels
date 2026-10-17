"""T006: v1 edit scripts and quick renders must look exactly as they did in v0.1.0 (SC-005).

References in tests/golden/v1 were produced by tests/golden/v1/generate_v1.py from main @ 6e23914.
Never regenerate them with new code to make this pass.
"""
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from synthetic import synthetic_frame
from musclereels.exercises import ExerciseDB
from musclereels.layout import builtin_presets
from musclereels.project import Project, load_project, make_segment
from musclereels.render import SpriteCache, frame_for_time

GOLDEN = Path(__file__).parent / "golden" / "v1"
REPO = Path(__file__).resolve().parents[1]
CASES = json.loads((GOLDEN / "cases.json").read_text())


def project_for(case) -> Project:
    if case["kind"] == "script":
        return load_project(REPO / case["script"])
    seg = make_segment({"exercise": case["exercise"], "start": 0, "end": None,
                        "subtitle": case.get("subtitle")}, ExerciseDB())
    return Project(input=Path("x.mp4"), segments=[seg], layout=builtin_presets()[f"card-{case['position']}"])


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_matches_v1_output(case):
    project = project_for(case)
    cache = SpriteCache()
    for t in case["times"]:
        expected = cv2.imread(str(GOLDEN / f"{case['name']}_t{t:.2f}.png"))
        got = frame_for_time(project, t, source_frame=synthetic_frame(t, tuple(case["source_size"])), cache=cache)
        assert got.shape == expected.shape
        diff = int(np.abs(got.astype(np.int16) - expected.astype(np.int16)).max())
        assert diff <= 1, f"{case['name']} at t={t}: max pixel diff {diff}"
