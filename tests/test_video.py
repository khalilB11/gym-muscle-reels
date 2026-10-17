"""T009: VideoSource probing, exact frame access, VFR proxy, fit_frame."""
import cv2
import numpy as np
import pytest

from musclereels.video import VideoSource, fit_frame


def sequential(path, index):
    cap = cv2.VideoCapture(str(path))
    for _ in range(index + 1):
        ok, frame = cap.read()
        assert ok
    cap.release()
    return frame


def test_info(demo_clip):
    info = VideoSource(demo_clip).info
    assert info.duration == pytest.approx(3.0, abs=0.05)
    assert info.fps == pytest.approx(30.0)
    assert info.size == (720, 1280)
    assert info.has_audio is True
    assert info.needs_proxy is False


def test_silent_clip_has_no_audio(silent_clip):
    assert VideoSource(silent_clip).info.has_audio is False


@pytest.mark.parametrize("t, index", [(1.5, 45), (0.0, 0), (2.9, 87), (0.51, 15)])
def test_frame_at_is_exact(demo_clip, t, index):
    src = VideoSource(demo_clip)
    assert np.array_equal(src.frame_at(t), sequential(demo_clip, index))


def test_random_access_in_any_order(demo_clip):
    src = VideoSource(demo_clip)
    for t, i in [(2.0, 60), (0.2, 6), (1.0, 30)]:
        assert np.array_equal(src.frame_at(t), sequential(demo_clip, i))


def test_iter_frames(demo_clip):
    frames = list(VideoSource(demo_clip).iter_frames(1.0, 1.5))
    assert len(frames) == 15
    t0, f0 = frames[0]
    assert t0 == pytest.approx(1.0) and np.array_equal(f0, sequential(demo_clip, 30))


def test_vfr_needs_proxy_and_is_exact_after_prepare(vfr_clip):
    src = VideoSource(vfr_clip)
    assert src.info.needs_proxy is True
    calls = []
    src.prepare(progress_cb=calls.append)
    assert src.path != vfr_clip and src.path.exists() and ".musclereels-cache" in str(src.path)
    assert calls and calls[-1] == pytest.approx(1.0)
    assert np.array_equal(src.frame_at(1.0), sequential(src.path, round(1.0 * src.info.fps)))
    assert VideoSource(vfr_clip).prepare() is None   # cached proxy reused


@pytest.mark.parametrize("shape", [(1280, 720, 3), (720, 1280, 3), (1080, 1080, 3)])
def test_fit_frame(shape):
    assert fit_frame(np.zeros(shape, np.uint8)).shape == (1920, 1080, 3)
    assert fit_frame(np.zeros(shape, np.uint8), out_size=(540, 960)).shape == (960, 540, 3)
