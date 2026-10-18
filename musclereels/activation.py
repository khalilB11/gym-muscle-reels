"""Which muscles light up, at Simple (18 groups) or Detailed (40 muscles) level.

Rules (data-model.md "Exercise"):
  * Naming a group lights its *default* members; naming a muscle lights that muscle.
  * Precedence: specific primary > specific secondary > group primary > group secondary,
    so `primary: [chest], secondary: [mid_chest]` makes the mid chest secondary.
  * Segment click overrides (`muscle: primary|secondary|off`) are applied last.
  * Simple level: a group is primary if any of its default members is primary, else secondary
    if any is secondary. Non-default members (hip flexors, tibialis, ...) don't light their group.
Order follows the order the muscles were named in, so legends read naturally.
"""
from __future__ import annotations

from typing import Iterable, Mapping

from .muscles import registry


def activate(primary_refs: Iterable[str], secondary_refs: Iterable[str],
             overrides: Mapping[str, str] | None, level: str) -> tuple[list[str], list[str]]:
    reg = registry()
    p_refs, s_refs = reg.resolve(primary_refs), reg.resolve(secondary_refs)
    order: list[str] = []

    def note(ms):
        for m in ms:
            if m not in order:
                order.append(m)

    state: dict[str, str] = {}
    for refs in (p_refs, s_refs):
        for r in refs:
            note(reg.expand(r))
    for refs, lvl, specific in ((s_refs, "secondary", False), (p_refs, "primary", False),
                                (s_refs, "secondary", True), (p_refs, "primary", True)):
        for r in refs:
            if reg.is_group(r) != (not specific):
                continue
            for m in reg.expand(r):
                state[m] = lvl
    for ref, lvl in (overrides or {}).items():
        for r in reg.resolve([ref]):
            for m in reg.expand(r):
                if lvl == "off":
                    state.pop(m, None)
                else:
                    state[m] = lvl
                    note([m])

    if level == "detailed":
        return ([m for m in order if state.get(m) == "primary"],
                [m for m in order if state.get(m) == "secondary"])

    groups: list[str] = []
    gstate: dict[str, str] = {}
    for m in order:
        if m not in state or not reg.get(m).default:
            continue
        g = reg.group_of(m)
        if g not in groups:
            groups.append(g)
        if state[m] == "primary" or g not in gstate:
            gstate[g] = state[m] if gstate.get(g) != "primary" else "primary"
    return ([g for g in groups if gstate[g] == "primary"], [g for g in groups if gstate[g] == "secondary"])


def simple_groups_of(muscles: Iterable[str]) -> list[str]:
    """Groups for a list of ids (groups pass through), order kept, duplicates dropped."""
    reg = registry()
    out: list[str] = []
    for m in muscles:
        g = m if reg.is_group(m) else reg.group_of(m)
        if g not in out:
            out.append(g)
    return out
