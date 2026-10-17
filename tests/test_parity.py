"""T021: the preview path (frame_for_time) and the export path (render) produce the same picture (SC-004).

Export is H.264 with 4:2:0 chroma subsampling, which alone costs ~31 dB on the colourful test pattern,
so frames are compared on luma (Y): PSNR >= 40 dB. The matching export frame must also be clearly
closer than its neighbours, which catches off-by-one-frame timing bugs.
"""
from pathlib import Path

import cv2
import numpy as np
import pytest

from musclereels.exercises import ExerciseDB
from musclereels.project import Project, make_segment
from musclereels.render import SpriteCache, frame_for_time, render
from musclereels.video import VideoSource


def luma(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2YUV)[..., 0]


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    return 99.0 if mse == 0 else 10 * np.log10(255 ** 2 / mse)


@pytest.mark.parametrize("layout_name", ["card-left", "split-corners"])
def test_preview_matches_export(demo_clip, tmp_path, layout_name):
    from musclereels.layout import builtin_presets
    db = ExerciseDB()
    project = Project(
        input=demo_clip, output=tmp_path / "out.mp4", crf=10, preset="ultrafast",
        layout=builtin_presets()[layout_name],
        segments=[make_segment({"exercise": "squat", "start": 0, "end": 1.6, "subtitle": "5 x 5"}, db),
                  make_segment({"exercise": "pull_up", "start": 1.6, "end": None}, db)])
    out = render(project)
    exported = VideoSource(out)
    source = VideoSource(demo_clip)
    cache = SpriteCache()
    for t in (0.4, 1.0, 2.5):
        preview = frame_for_time(project, t, video=source, cache=cache)
        i = exported.index_at(t)
        frame = exported.read_index(i)
        assert frame.shape == preview.shape
        score = psnr(luma(frame), luma(preview))
        assert score >= 40, f"t={t}: luma PSNR {score:.1f} dB"
        for j in (i - 1, i + 1):
            assert psnr(luma(exported.read_index(j)), luma(preview)) < score - 6, f"t={t}: frame offset suspected"


def test_half_scale_preview_is_the_export_frame_downscaled(demo_clip):
    project = Project(input=demo_clip, segments=[make_segment({"exercise": "deadlift", "start": 0, "end": None},
                                                              ExerciseDB())])
    src = VideoSource(demo_clip)
    full = frame_for_time(project, 1.2, video=src)
    half = frame_for_time(project, 1.2, video=src, scale=0.5)
    assert half.shape == (960, 540, 3)
    ref = cv2.resize(full, (540, 960), interpolation=cv2.INTER_AREA)
    assert psnr(ref, half) >= 30
