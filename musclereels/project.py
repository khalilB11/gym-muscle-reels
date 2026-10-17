"""Edit scripts: which exercise is on screen when."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .bodymap import resolve_muscles
from .exercises import ExerciseDB
from .overlay import POSITIONS
from .theme import Theme

FITS = ("auto", "cover", "blur")


def parse_time(value) -> float:
    """Accepts seconds (6.5) or timestamps ('0:06.5', '1:02:03')."""
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


@dataclass
class Segment:
    start: float
    end: float
    title: str
    primary: list[str]
    secondary: list[str] = field(default_factory=list)
    subtitle: str | None = None


@dataclass
class Job:
    input: Path
    output: Path
    segments: list[Segment]
    position: str = "left"
    fit: str = "auto"
    trim: bool = False
    card_scale: float = 1.0
    pulse_hz: float = 1.2
    crf: int = 18
    preset: str = "medium"
    audio: bool = True
    theme: Theme = field(default_factory=Theme)

    def validate(self) -> None:
        if self.position not in POSITIONS:
            raise ValueError(f"position must be one of {POSITIONS}")
        if self.fit not in FITS:
            raise ValueError(f"fit must be one of {FITS}")
        if not self.segments:
            raise ValueError("at least one segment is required")
        self.segments.sort(key=lambda s: s.start)
        for a, b in zip(self.segments, self.segments[1:]):
            if b.start < a.end:
                raise ValueError(f"segments overlap: '{a.title}' ends at {a.end}s, '{b.title}' starts at {b.start}s")
        for s in self.segments:
            if s.end <= s.start:
                raise ValueError(f"segment '{s.title}' ends before it starts")


def make_segment(spec: dict, db: ExerciseDB) -> Segment:
    start, end = parse_time(spec.get("start", 0)), parse_time(spec.get("end"))
    if "exercise" in spec:
        ex = db.get(spec["exercise"])
        title, primary, secondary = ex.name, list(ex.primary), list(ex.secondary)
    else:
        title, primary, secondary = "", [], []
    # Inline overrides / fully custom segments.
    if "primary" in spec:
        primary = resolve_muscles(spec["primary"])
    if "secondary" in spec:
        secondary = resolve_muscles(spec["secondary"])
    secondary = [m for m in secondary if m not in primary]
    title = spec.get("title", title)
    if not title or not primary:
        raise ValueError(f"segment at {start}s needs an `exercise`, or a `title` and `primary` muscles")
    return Segment(start, end, title, primary, secondary, spec.get("subtitle"))


def load_job(path: str | Path, overrides: dict | None = None) -> Job:
    path = Path(path)
    data = yaml.safe_load(path.read_text("utf-8")) or {}
    data.update({k: v for k, v in (overrides or {}).items() if v is not None})
    base = path.parent

    def rel(p) -> Path:
        p = Path(p).expanduser()
        return p if p.is_absolute() else base / p

    extra = data.get("exercises_file") or []
    if isinstance(extra, str):
        extra = [extra]
    db = ExerciseDB([rel(f) for f in extra])
    if "input" not in data:
        raise ValueError(f"{path}: `input` (the source video) is required")
    inp = rel(data["input"])
    job = Job(
        input=inp,
        output=rel(data.get("output", inp.with_name(inp.stem + "_reel.mp4"))),
        segments=[make_segment(s, db) for s in data.get("segments", [])],
        position=data.get("position", "left"),
        fit=data.get("fit", "auto"),
        trim=bool(data.get("trim", False)),
        card_scale=float(data.get("card_scale", 1.0)),
        pulse_hz=float(data.get("pulse_hz", 1.2)),
        crf=int(data.get("crf", 18)),
        preset=data.get("preset", "medium"),
        audio=bool(data.get("audio", True)),
        theme=Theme.from_dict(data.get("theme")),
    )
    job.validate()
    return job
