import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))  # for `from synthetic import ...`

REPO = Path(__file__).resolve().parents[1]


def pytest_addoption(parser):
    parser.addoption("--update-golden", action="store_true", help="rewrite golden reference images")


@pytest.fixture(scope="session")
def update_golden(request) -> bool:
    return request.config.getoption("--update-golden")


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pytest.skip("ffmpeg not available")
    return exe


def _make_clip(path: Path, w: int, h: int, secs: float = 3.0, fps: int = 30, audio: bool = True,
               extra_vf: str = "") -> Path:
    cmd = [_ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate={fps}:duration={secs}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={secs}"]
    if extra_vf:
        cmd += ["-vf", extra_vf]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-g", "15", "-pix_fmt", "yuv420p"]
    cmd += (["-c:a", "aac", "-shortest"] if audio else [])
    cmd += [str(path)]
    subprocess.run(cmd, check=True)
    return path


@pytest.fixture(scope="session")
def demo_clip(tmp_path_factory) -> Path:
    """3 s, 720x1280 portrait, 30 fps, with a 440 Hz tone."""
    return _make_clip(tmp_path_factory.mktemp("clips") / "demo.mp4", 720, 1280)


@pytest.fixture(scope="session")
def landscape_clip(tmp_path_factory) -> Path:
    return _make_clip(tmp_path_factory.mktemp("clips") / "landscape.mp4", 1280, 720)


@pytest.fixture(scope="session")
def silent_clip(tmp_path_factory) -> Path:
    return _make_clip(tmp_path_factory.mktemp("clips") / "silent.mp4", 720, 1280, audio=False)


@pytest.fixture(scope="session")
def vfr_clip(tmp_path_factory) -> Path:
    """Variable frame rate: timestamps jitter like phone footage."""
    path = tmp_path_factory.mktemp("clips") / "vfr.mp4"
    src = _make_clip(path.with_name("cfr_src.mp4"), 720, 1280, audio=False)
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", str(src),
                    # first 1.5 s at 30 fps, then 20 fps: avg_frame_rate != r_frame_rate
                    "-vf", "setpts='if(lt(N,45),N/30,1.5+(N-45)/20)/TB'", "-fps_mode", "vfr",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path
