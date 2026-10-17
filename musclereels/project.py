"""Edit scripts (project files): which exercise is on screen when, and how it looks.

Format: specs/002-editor-ui-detailed-muscles/contracts/edit-script-v2.md
v1 files (no `version` key) load unchanged and render exactly as in v0.1.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .bodymap import resolve_muscles
from .exercises import ExerciseDB
from .layout import Layout, LayoutError, SegmentLayoutOverride, builtin_presets, preset_name, resolve_preset
from .theme import Theme

FITS = ("auto", "cover", "blur")
DETAIL_LEVELS = ("simple", "detailed")
OVERRIDE_STATES = ("primary", "secondary", "off")

TOP_KEYS = {"version", "input", "output", "position", "fit", "trim", "card_scale", "pulse_hz", "crf",
            "preset", "audio", "theme", "exercises_file", "segments", "detail_level", "layout"}
SEGMENT_KEYS = {"start", "end", "exercise", "title", "subtitle", "primary", "secondary",
                "overrides", "layout", "insets"}


class ProjectError(ValueError):
    def __init__(self, message: str, file: Optional[Path] = None, line: Optional[int] = None):
        self.message, self.file, self.line = message, file, line
        where = f"{file}:{line}: " if file and line else (f"{file}: " if file else "")
        super().__init__(where + message)


def parse_time(value) -> float:
    """Accepts seconds (6.5) or timestamps ('0:06.5', '1:02:03'); None/'end' = until the end."""
    if value is None:
        return math.inf
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().lower()
    if s in ("end", "inf", ""):
        return math.inf
    total = 0.0
    for part in s.split(":"):
        total = total * 60 + float(part)
    return total


def _fmt_time(t: float):
    return "end" if math.isinf(t) else (int(t) if float(t).is_integer() else round(t, 3))


@dataclass
class Segment:
    start: float
    end: float
    title: str
    primary: list[str]
    secondary: list[str] = field(default_factory=list)
    subtitle: Optional[str] = None
    # What the user wrote (kept so saving reproduces the file faithfully):
    exercise: Optional[str] = None
    title_set: Optional[str] = None
    primary_set: Optional[list[str]] = None
    secondary_set: Optional[list[str]] = None
    overrides: dict[str, str] = field(default_factory=dict)
    layout: Optional[SegmentLayoutOverride] = None
    insets: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"start": _fmt_time(self.start), "end": _fmt_time(self.end)}
        if self.exercise:
            d["exercise"] = self.exercise
        if self.title_set is not None:
            d["title"] = self.title_set
        if self.subtitle:
            d["subtitle"] = self.subtitle
        if self.primary_set is not None:
            d["primary"] = list(self.primary_set)
        if self.secondary_set is not None:
            d["secondary"] = list(self.secondary_set)
        if self.overrides:
            d["overrides"] = dict(self.overrides)
        if self.layout:
            d["layout"] = self.layout.to_dict()
        if self.insets:
            d["insets"] = [dict(i) for i in self.insets]
        return d


def make_segment(spec: dict, db: ExerciseDB) -> Segment:
    start, end = parse_time(spec.get("start", 0)), parse_time(spec.get("end"))
    exercise = spec.get("exercise")
    if exercise:
        ex = db.get(exercise)
        title, primary, secondary = ex.name, list(ex.primary), list(ex.secondary)
    else:
        title, primary, secondary = "", [], []
    primary_set = secondary_set = None
    if spec.get("primary") is not None:
        primary_set = list(spec["primary"])
        primary = resolve_muscles(primary_set)
    if spec.get("secondary") is not None:
        secondary_set = list(spec["secondary"])
        secondary = resolve_muscles(secondary_set)
    secondary = [m for m in secondary if m not in primary]
    title_set = spec.get("title")
    title = title_set if title_set else title
    if not title or not primary:
        raise ValueError(f"segment at {start}s needs an `exercise`, or a `title` and `primary` muscles")
    overrides = dict(spec.get("overrides") or {})
    for m, state in overrides.items():
        resolve_muscles([m])
        if state not in OVERRIDE_STATES:
            raise ValueError(f"override for '{m}' must be one of {OVERRIDE_STATES}")
    layout = SegmentLayoutOverride.from_dict(spec["layout"]) if spec.get("layout") else None
    return Segment(start, end, title, primary, secondary, spec.get("subtitle"), exercise, title_set,
                   primary_set, secondary_set, overrides, layout, list(spec.get("insets") or []))


def _default_layout() -> Layout:
    return builtin_presets()["card-left"]


@dataclass
class Project:
    input: Path
    segments: list[Segment]
    output: Optional[Path] = None
    version: int = 2
    layout: Layout = field(default_factory=_default_layout)
    detail_level: str = "simple"
    fit: str = "auto"
    trim_to_segments: bool = False
    trim_in: Optional[float] = None
    trim_out: Optional[float] = None
    card_scale: float = 1.0
    pulse_hz: float = 1.2
    crf: int = 18
    preset: str = "medium"
    audio: bool = True
    theme: Theme = field(default_factory=Theme)
    exercises_file: list[Path] = field(default_factory=list)
    path: Optional[Path] = field(default=None, compare=False)   # where it was loaded from / saved to

    def __post_init__(self):
        if self.output is None and self.input is not None:
            inp = Path(self.input)
            self.output = inp.with_name(inp.stem + "_reel.mp4")

    # -- queries --------------------------------------------------------------
    def segment_at(self, t: float) -> Optional[Segment]:
        for s in self.segments:
            if s.start <= t < s.end:
                return s
        return None

    def time_range(self, duration: float = math.inf) -> tuple[float, float]:
        """Export range: trim in/out, or first..last segment when trim_to_segments."""
        if self.trim_to_segments and self.segments:
            return self.segments[0].start, min(self.segments[-1].end, duration)
        t0 = self.trim_in or 0.0
        t1 = min(self.trim_out if self.trim_out is not None else math.inf, duration)
        return t0, t1

    def validate(self) -> None:
        if self.fit not in FITS:
            raise ProjectError(f"fit must be one of {FITS}", self.path)
        if self.detail_level not in DETAIL_LEVELS:
            raise ProjectError(f"detail_level must be one of {DETAIL_LEVELS}", self.path)
        if not self.segments:
            raise ProjectError("at least one segment is required", self.path)
        self.segments.sort(key=lambda s: s.start)
        for s in self.segments:
            if s.start < 0:
                raise ProjectError(f"segment '{s.title}': start must be ≥ 0", self.path)
            if s.end <= s.start:
                raise ProjectError(f"segment '{s.title}' ends before it starts", self.path)
        for a, b in zip(self.segments, self.segments[1:]):
            if b.start < a.end:
                raise ProjectError(f"segments overlap: '{a.title}' ends at {a.end}s, '{b.title}' starts at {b.start}s",
                                   self.path)
        if self.trim_in is not None and self.trim_out is not None and self.trim_out <= self.trim_in:
            raise ProjectError("trim: `out` must be after `in`", self.path)


# Backwards-compatible name used by v0.1 code.
Job = Project


# --- loading ---------------------------------------------------------------------

def _lines(node) -> dict:
    """{key: line} for a YAML mapping node (1-based lines)."""
    if not isinstance(node, yaml.MappingNode):
        return {}
    return {k.value: k.start_mark.line + 1 for k, _ in node.value if isinstance(k, yaml.ScalarNode)}


def _norm(base: Path, p) -> Path:
    p = Path(str(p)).expanduser()
    return p if p.is_absolute() else Path(os.path.normpath(base / p))


def load_project(path: str | Path, overrides: dict | None = None) -> Project:
    path = Path(path)
    text = path.read_text("utf-8")
    try:
        root = yaml.compose(text)
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        raise ProjectError(f"invalid YAML: {e}", path) from None
    if not isinstance(data, dict):
        raise ProjectError("an edit script must be a mapping of keys", path)
    lines = _lines(root)
    seg_nodes = []
    if isinstance(root, yaml.MappingNode):
        for k, v in root.value:
            if k.value == "segments" and isinstance(v, yaml.SequenceNode):
                seg_nodes = v.value

    for k in data:
        if k not in TOP_KEYS:
            raise ProjectError(f"unknown key '{k}'", path, lines.get(k))
    data.update({k: v for k, v in (overrides or {}).items() if v is not None})
    version = int(data.get("version", 1))
    if version not in (1, 2):
        raise ProjectError(f"unsupported version {version}", path, lines.get("version"))
    base = path.parent

    extra = data.get("exercises_file") or []
    extra = [extra] if isinstance(extra, str) else list(extra)
    exercise_files = [_norm(base, f) for f in extra]
    try:
        db = ExerciseDB(exercise_files)
    except (ValueError, FileNotFoundError) as e:
        raise ProjectError(str(e), path, lines.get("exercises_file")) from None

    if "input" not in data:
        raise ProjectError("`input` (the source video) is required", path)
    inp = _norm(base, data["input"])

    segments = []
    for i, spec in enumerate(data.get("segments") or []):
        node = seg_nodes[i] if i < len(seg_nodes) else None
        seg_lines = _lines(node)
        seg_line = node.start_mark.line + 1 if node is not None else lines.get("segments")
        if not isinstance(spec, dict):
            raise ProjectError("each segment must be a mapping", path, seg_line)
        for k in spec:
            if k not in SEGMENT_KEYS:
                raise ProjectError(f"unknown segment key '{k}'", path, seg_lines.get(k, seg_line))
        try:
            segments.append(make_segment(spec, db))
        except (KeyError, ValueError) as e:
            msg = e.args[0] if e.args else str(e)
            raise ProjectError(msg, path, seg_line) from None

    # layout: v1 `position` -> card preset; v2 preset name or object
    try:
        if "layout" in data:
            lay = data["layout"]
            layout = resolve_preset(lay, base) if isinstance(lay, str) else Layout.from_dict(lay)
        else:
            pos = data.get("position", "left")
            layout = builtin_presets()[f"card-{pos}"] if f"card-{pos}" in builtin_presets() else None
            if layout is None:
                raise LayoutError(f"position must be one of left, right, center")
    except LayoutError as e:
        raise ProjectError(str(e), path, lines.get("layout", lines.get("position"))) from None

    trim = data.get("trim", False)
    trim_to_segments, trim_in, trim_out = False, None, None
    if isinstance(trim, dict):
        bad = set(trim) - {"in", "out"}
        if bad:
            raise ProjectError(f"unknown trim key(s): {', '.join(sorted(bad))}", path, lines.get("trim"))
        trim_in = parse_time(trim["in"]) if trim.get("in") is not None else None
        trim_out = parse_time(trim["out"]) if trim.get("out") is not None else None
    else:
        trim_to_segments = bool(trim)

    project = Project(
        input=inp,
        output=_norm(base, data["output"]) if data.get("output") else None,
        segments=segments,
        version=version,
        layout=layout,
        detail_level=data.get("detail_level", "simple"),
        fit=data.get("fit", "auto"),
        trim_to_segments=trim_to_segments, trim_in=trim_in, trim_out=trim_out,
        card_scale=float(data.get("card_scale", 1.0)),
        pulse_hz=float(data.get("pulse_hz", 1.2)),
        crf=int(data.get("crf", 18)),
        preset=data.get("preset", "medium"),
        audio=bool(data.get("audio", True)),
        theme=Theme.from_dict(data.get("theme")),
        exercises_file=exercise_files,
        path=path,
    )
    try:
        project.validate()
    except ProjectError as e:
        line = lines.get("detail_level") if "detail_level" in e.message else lines.get("segments")
        raise ProjectError(e.message, path, line) from None
    return project


def _rel(p: Path, base: Path) -> str:
    try:
        return Path(os.path.relpath(p, base)).as_posix()
    except ValueError:          # different drive on Windows
        return str(p)


def save_project(project: Project, path: str | Path) -> None:
    """Write a v2 edit script. Paths are stored relative to the file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    base = path.parent.resolve()
    d: dict[str, Any] = {"version": 2, "input": _rel(Path(project.input).resolve(), base)}
    if project.output:
        d["output"] = _rel(Path(project.output).resolve(), base)
    if project.trim_to_segments:
        d["trim"] = True
    elif project.trim_in is not None or project.trim_out is not None:
        d["trim"] = {k: _fmt_time(v) for k, v in (("in", project.trim_in), ("out", project.trim_out)) if v is not None}
    d["detail_level"] = project.detail_level
    d["layout"] = preset_name(project.layout) or project.layout.to_dict()
    defaults = Project(input=Path("x"), segments=[])
    for key in ("fit", "card_scale", "pulse_hz", "crf", "preset", "audio"):
        val = getattr(project, key)
        if val != getattr(defaults, key):
            d[key] = val
    theme = project.theme.to_dict(only_changed=True)
    if theme:
        d["theme"] = theme
    if project.exercises_file:
        d["exercises_file"] = [_rel(Path(f).resolve(), base) for f in project.exercises_file]
    d["segments"] = [s.to_dict() for s in project.segments]
    path.write_text(yaml.safe_dump(d, sort_keys=False, allow_unicode=True), "utf-8")
    project.path = path


# v0.1 name
load_job = load_project
