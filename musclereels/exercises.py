"""Exercise database: which muscles each movement works."""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Iterable

import yaml

from .bodymap import normalize, resolve_muscles


@dataclass(frozen=True)
class Exercise:
    key: str
    name: str
    primary: tuple[str, ...]
    secondary: tuple[str, ...] = ()


class ExerciseDB:
    """Built-in exercises, optionally extended/overridden by user YAML files."""

    def __init__(self, extra_files: Iterable[str | Path] = ()):
        self._items: dict[str, Exercise] = {}
        self._aliases: dict[str, str] = {}
        builtin = resources.files("musclereels").joinpath("data/exercises.yaml").read_text("utf-8")
        self._load(yaml.safe_load(builtin), "built-in")
        for f in extra_files:
            self._load(yaml.safe_load(Path(f).read_text("utf-8")) or {}, str(f))

    def _load(self, data: dict, source: str) -> None:
        for key, spec in data.items():
            k = normalize(key)
            try:
                ex = Exercise(
                    key=k,
                    name=spec.get("name", key.replace("_", " ").title()),
                    primary=tuple(resolve_muscles(spec.get("primary", []))),
                    secondary=tuple(resolve_muscles(spec.get("secondary", []))),
                )
            except ValueError as e:
                raise ValueError(f"{source}: exercise '{key}': {e}") from None
            # A muscle listed as primary shouldn't also show as secondary.
            ex = Exercise(ex.key, ex.name, ex.primary, tuple(m for m in ex.secondary if m not in ex.primary))
            self._items[k] = ex
            for alias in spec.get("aliases", []):
                self._aliases[normalize(alias)] = k

    def get(self, name: str) -> Exercise:
        k = normalize(name)
        k = k if k in self._items else self._aliases.get(k, k)
        if k in self._items:
            return self._items[k]
        options = list(self._items) + list(self._aliases)
        close = difflib.get_close_matches(k, options, n=3, cutoff=0.5)
        hint = f" Did you mean: {', '.join(close)}?" if close else " Run `musclereels list` to see all."
        raise KeyError(f"Unknown exercise '{name}'.{hint}")

    def all(self) -> list[Exercise]:
        return list(self._items.values())

    def aliases_of(self, key: str) -> list[str]:
        return [a for a, k in self._aliases.items() if k == key]

    def search(self, query: str, limit: int = 50) -> list[Exercise]:
        """Exercises matching a name, key or alias; prefix matches first, then substrings,
        then close (misspelt) matches."""
        q = normalize(query)
        if not q:
            return sorted(self.all(), key=lambda e: e.name)[:limit]
        prefix, contains = [], []
        for ex in self.all():
            names = [ex.key, normalize(ex.name), *self.aliases_of(ex.key)]
            if any(n.startswith(q) for n in names):
                prefix.append(ex)
            elif any(q in n for n in names):
                contains.append(ex)
        found = sorted(prefix, key=lambda e: e.name) + sorted(contains, key=lambda e: e.name)
        if not found:
            options = list(self._items) + list(self._aliases)
            for k in difflib.get_close_matches(q, options, n=5, cutoff=0.6):
                ex = self._items.get(k) or self._items[self._aliases[k]]
                if ex not in found:
                    found.append(ex)
        return found[:limit]
