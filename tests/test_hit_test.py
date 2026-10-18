"""T045: which muscle is under the mouse (design coordinates 200x440)."""
import numpy as np
import pytest

from musclereels.bodymap import DETAILED, W, hit_test


def centroid(poly):
    pts = np.array(poly)
    return float(pts[:, 0].mean()), float(pts[:, 1].mean())


@pytest.mark.parametrize("view, muscle", [("front", "upper_chest"), ("front", "vastus_medialis"),
                                          ("back", "gluteus_medius"), ("back", "triceps_long_head"),
                                          ("front", "brachialis"), ("back", "soleus")])
def test_hits_each_side(view, muscle):
    polys = DETAILED[view][muscle]
    for poly in polys:                      # right and mirrored left side
        x, y = centroid(poly)
        assert hit_test(view, x, y, "detailed") == muscle


def test_simple_level_returns_group():
    x, y = centroid(DETAILED["front"]["upper_chest"][0])
    assert hit_test("front", x, y, "simple") == "chest"


def test_outside_the_body_is_none():
    assert hit_test("front", 5, 5, "detailed") is None
    assert hit_test("back", W - 3, 430, "simple") is None
