"""Muscle registry: Simple groups, Detailed muscles and aliases (data in data/muscles.yaml)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Iterable

import yaml

LEVELS = ("simple", "detailed")


def normalize(name: str) -> str:
    return re.sub(r"[\s\-]+", "_", str(name).strip().lower())


@dataclass(frozen=True)
class Muscle:
    id: str
    short_name: str
    full_name: str
    group: str                        # parent Simple group id (== id for groups)
    views: tuple[str, ...] = field(default=())
    default: bool = True              # lit when only its group is named; shown at Simple level


class MuscleRegistry:
    def __init__(self, data: dict):
        self.groups: dict[str, Muscle] = {}
        for gid, spec in (data.get("groups") or {}).items():
            name = spec["name"]
            self.groups[gid] = Muscle(gid, name, spec.get("full_name", name), gid)
        self.detailed: dict[str, Muscle] = {}
        for mid, spec in (data.get("muscles") or {}).items():
            if spec["group"] not in self.groups:
                raise ValueError(f"muscle '{mid}' has unknown group '{spec['group']}'")
            if mid in self.groups:
                raise ValueError(f"muscle id '{mid}' clashes with a group id")
            self.detailed[mid] = Muscle(mid, spec["short_name"], spec["full_name"], spec["group"],
                                        tuple(spec.get("views", ())), bool(spec.get("default", True)))
        self.aliases: dict[str, list[str]] = {normalize(k): v for k, v in (data.get("aliases") or {}).items()}

    # -- lookup -------------------------------------------------------------
    def muscles(self, level: str = "simple") -> list[Muscle]:
        if level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}")
        return list(self.groups.values()) if level == "simple" else list(self.detailed.values())

    def get(self, mid: str) -> Muscle:
        return self.groups.get(mid) or self.detailed[mid]

    def group_of(self, mid: str) -> str:
        return self.get(mid).group

    def members(self, gid: str, default_only: bool = False) -> list[str]:
        """Detailed muscles in a group."""
        return [m.id for m in self.detailed.values() if m.group == gid and (m.default or not default_only)]

    def is_group(self, mid: str) -> bool:
        return mid in self.groups

    def expand(self, ref: str) -> list[str]:
        """Detailed muscles a resolved id stands for: a group -> its default members, a muscle -> itself."""
        return self.members(ref, default_only=True) if ref in self.groups else [ref]

    def known(self) -> list[str]:
        return sorted(self.groups) + sorted(self.detailed) + sorted(self.aliases)

    def display_name(self, mid: str) -> str:
        return self.get(mid).short_name

    # -- resolution ---------------------------------------------------------
    def resolve(self, refs: Iterable[str]) -> list[str]:
        """Expand aliases, validate and de-duplicate (order kept). Returns group/muscle ids as named."""
        out: list[str] = []
        for raw in refs:
            key = normalize(raw)
            for m in self.aliases.get(key, [key]):
                if m not in self.groups and m not in self.detailed:
                    raise ValueError(f"Unknown muscle '{raw}'. Known: {', '.join(self.known())}")
                if m not in out:
                    out.append(m)
        return out


@lru_cache(maxsize=1)
def registry() -> MuscleRegistry:
    text = resources.files("musclereels").joinpath("data/muscles.yaml").read_text("utf-8")
    return MuscleRegistry(yaml.safe_load(text))
