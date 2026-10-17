"""T007: edit script v2 schema, v1 migration, round-trip and validation."""
import textwrap
from pathlib import Path

import pytest

from musclereels.layout import builtin_presets
from musclereels.project import ProjectError, load_project, save_project


def write(tmp_path: Path, text: str, name="p.yaml") -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(text), "utf-8")
    return p


def test_v1_position_maps_to_card_preset(tmp_path):
    p = write(tmp_path, """
        input: clip.mp4
        position: right
        segments:
          - {start: 0, end: 4, exercise: squat}
    """)
    proj = load_project(p)
    assert proj.version == 1
    assert proj.layout == builtin_presets()["card-right"]
    assert proj.detail_level == "simple"
    assert proj.input == tmp_path / "clip.mp4"


def test_v1_defaults_to_card_left(tmp_path):
    proj = load_project(write(tmp_path, "input: clip.mp4\nsegments: [{start: 0, end: 2, exercise: bench}]\n"))
    assert proj.layout == builtin_presets()["card-left"]


def test_v2_round_trip(tmp_path):
    p = write(tmp_path, """
        version: 2
        input: clips/a.mp4
        output: out/a_reel.mp4
        trim: {in: "0:02", out: 9.5}
        detail_level: detailed
        layout:
          card: per_element
          labels: false
          title:  {visible: true, x: 60, y: 250, width: 960}
          front:  {visible: true, x: 60, y: 900, width: 240}
          back:   {visible: false, x: 700, y: 420, width: 200}
          legend: {visible: true, x: 60, y: 1300, width: 600}
        segments:
          - start: 0
            end: 4
            exercise: incline press
            subtitle: "4 x 8"
            layout: {back: {visible: true}}
            overrides: {chest: secondary}
          - {start: 4, end: end, title: Sled Push, primary: [quads, glutes], secondary: [calves]}
    """)
    a = load_project(p)
    out = tmp_path / "copy" / "saved.yaml"
    save_project(a, out)
    text = out.read_text()
    assert "version: 2" in text
    assert "../clips/a.mp4" in text.replace("\\", "/")      # paths stay relative to the project file
    b = load_project(out)
    assert b.input == a.input and b.output == a.output
    assert (b.trim_in, b.trim_out) == (2.0, 9.5)
    assert b.layout == a.layout
    assert b.segments == a.segments
    assert b.detail_level == "detailed"


def test_v1_trim_bool_kept(tmp_path):
    p = write(tmp_path, "input: c.mp4\ntrim: true\nsegments: [{start: 1, end: 3, exercise: squat}]\n")
    proj = load_project(p)
    assert proj.trim_to_segments is True
    save_project(proj, tmp_path / "s.yaml")
    assert load_project(tmp_path / "s.yaml").trim_to_segments is True


def test_unknown_key_names_key_and_line(tmp_path):
    p = write(tmp_path, """
        version: 2
        input: c.mp4
        segments:
          - start: 0
            end: 3
            exercize: squat
    """)
    with pytest.raises(ProjectError) as e:
        load_project(p)
    assert "exercize" in str(e.value)
    assert e.value.line == 7 and e.value.file == p


def test_unknown_top_level_key(tmp_path):
    with pytest.raises(ProjectError, match="colour"):
        load_project(write(tmp_path, "input: c.mp4\ncolour: red\nsegments: [{start: 0, end: 1, exercise: squat}]\n"))


@pytest.mark.parametrize("segments, msg", [
    ("[{start: 0, end: 5, exercise: squat}, {start: 4, end: 8, exercise: deadlift}]", "overlap"),
    ("[{start: 3, end: 3, exercise: squat}]", "ends before"),
    ("[{start: -1, end: 3, exercise: squat}]", "start"),
])
def test_segment_validation(tmp_path, segments, msg):
    with pytest.raises(ProjectError, match=msg):
        load_project(write(tmp_path, f"input: c.mp4\nsegments: {segments}\n"))


def test_bad_detail_level(tmp_path):
    with pytest.raises(ProjectError, match="detail_level"):
        load_project(write(tmp_path, "version: 2\ninput: c.mp4\ndetail_level: ultra\nsegments: [{start: 0, end: 1, exercise: squat}]\n"))


def test_layout_preset_by_name(tmp_path):
    proj = load_project(write(tmp_path, "version: 2\ninput: c.mp4\nlayout: split-corners\nsegments: [{start: 0, end: 1, exercise: squat}]\n"))
    assert proj.layout == builtin_presets()["split-corners"]
