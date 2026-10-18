"""T043: Detailed muscle registry (data-model.md, research R6)."""
import pytest

from musclereels.bodymap import DETAILED
from musclereels.muscles import registry

PARENTS = {
    "upper_chest": "chest", "mid_chest": "chest", "lower_chest": "chest",
    "anterior_delt": "front_delts", "lateral_delt": "side_delts", "posterior_delt": "rear_delts",
    "upper_traps": "traps", "mid_traps": "traps", "lower_traps": "traps", "sternocleidomastoid": "traps",
    "rhomboid": "rhomboids", "infraspinatus": "rhomboids",
    "latissimus_dorsi": "lats", "teres_major": "lats",
    "erector_spinae": "lower_back",
    "biceps_long_head": "biceps", "biceps_short_head": "biceps", "brachialis": "biceps",
    "triceps_long_head": "triceps", "triceps_lateral_head": "triceps", "triceps_medial_head": "triceps",
    "brachioradialis": "forearms", "wrist_flexors": "forearms", "wrist_extensors": "forearms",
    "upper_abs": "abs", "lower_abs": "abs",
    "external_obliques": "obliques", "serratus_anterior": "obliques",
    "gluteus_maximus": "glutes", "gluteus_medius": "glutes",
    "rectus_femoris": "quads", "vastus_lateralis": "quads", "vastus_medialis": "quads", "hip_flexors": "quads",
    "biceps_femoris": "hamstrings", "medial_hamstrings": "hamstrings",
    "hip_adductors": "adductors",
    "gastrocnemius": "calves", "soleus": "calves", "tibialis_anterior": "calves",
}
NOT_DEFAULT = {"sternocleidomastoid", "infraspinatus", "serratus_anterior", "hip_flexors", "tibialis_anterior"}


def test_forty_detailed_muscles_with_parents():
    reg = registry()
    muscles = {m.id: m for m in reg.muscles("detailed")}
    assert len(muscles) == 40
    assert {k: m.group for k, m in muscles.items()} == PARENTS


def test_names_and_views():
    for m in registry().muscles("detailed"):
        assert 0 < len(m.short_name) <= 16, m.id
        assert m.full_name and m.full_name != m.id
        assert m.views and set(m.views) <= {"front", "back"}
        for v in m.views:
            assert DETAILED[v].get(m.id), f"{m.id} has no shape in the {v} view"


def test_every_drawn_region_is_a_registered_muscle():
    ids = {m.id for m in registry().muscles("detailed")}
    for view, regions in DETAILED.items():
        assert set(regions) <= ids, set(regions) - ids


def test_group_expansion_uses_default_members_only():
    reg = registry()
    assert reg.expand("chest") == ["upper_chest", "mid_chest", "lower_chest"]
    assert "hip_flexors" not in reg.expand("quads")
    assert "tibialis_anterior" not in reg.expand("calves")
    for m in NOT_DEFAULT:
        assert reg.get(m).default is False
    for gid in reg.groups:
        assert reg.expand(gid), f"group {gid} has no default members"


@pytest.mark.parametrize("ref, expected", [("upper chest", ["upper_chest"]), ("shoulders",
                         ["anterior_delt", "lateral_delt", "posterior_delt"]), ("glutes", ["gluteus_maximus",
                                                                                        "gluteus_medius"])])
def test_resolve_and_expand(ref, expected):
    reg = registry()
    assert [m for r in reg.resolve([ref]) for m in reg.expand(r)] == expected
