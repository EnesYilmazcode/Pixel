"""Tests for the branch edits and for keeping each edit inside its region.

Run:  python -m pytest test_branches.py   (or)   python test_branches.py
"""
from __future__ import annotations

import re

import numpy as np
from PIL import Image, ImageFilter

import compose
from branch_pool import branches

_RNG = np.random.default_rng(2)
_ORIG = Image.fromarray(_RNG.integers(0, 255, (300, 200, 3)).astype("uint8")).filter(ImageFilter.GaussianBlur(2))
_BEFORE = {
    "target_box": [0.35, 0.3, 0.3, 0.3],
    "distractors": [
        {"desc": "Subway sign", "share": 0.36, "region": [0.4, 0.75, 0.2, 0.2]},
        {"desc": "lower-left region", "share": 0.07, "region": [0.0, 0.8, 0.2, 0.2]},
    ],
}


def test_one_removal_branch_per_thief_then_a_polish():
    pool = branches(_BEFORE, "Nike")
    assert len(pool) == 3
    assert "Subway sign" in pool[0]["directive"] and pool[0]["region"] == [_BEFORE["distractors"][0]["region"]]
    assert "lower-left region of the photo" in pool[1]["directive"]  # unnamed thief still targeted
    assert pool[2]["region"] == [_BEFORE["target_box"]]
    assert pool[0]["protect"] == [_BEFORE["target_box"]]  # a removal never touches the brand


def test_no_branch_adds_text_or_dims_the_scene():
    banned = ("headline", "call-to-action", "cta", "wordmark", "tagline", "dim", "darken",
              "tone down", "desaturate", "blur")
    for b in branches(_BEFORE, "Nike"):
        d = b["directive"].lower()
        assert not any(w in d for w in banned), d
        assert not re.search(r"add", d), d  # never asks to add anything


def test_ad_with_no_thieves_still_gets_a_branch():
    assert len(branches({"target_box": [0.3, 0.3, 0.3, 0.3], "distractors": []}, "Pepsi")) == 1


def test_keep_changes_takes_only_real_changes_near_the_region_and_off_the_brand():
    a = np.asarray(_ORIG).copy()
    edited = a.copy()
    edited[200:260, 20:80] = 0      # the removal, inside the branch region
    edited[20:60, 140:190] = 255    # drift far from the region
    edited[100:140, 80:110] = 255   # a change on the brand box
    out = np.asarray(compose.keep_changes(_ORIG, Image.fromarray(edited),
                                          near=[[0.1, 0.65, 0.3, 0.2]], protect=[[0.35, 0.3, 0.3, 0.3]]))
    assert out[230, 50].max() < 40                       # removal kept
    assert (out[40, 165] == a[40, 165]).all()            # far drift dropped
    assert (out[120, 95] == a[120, 95]).all()            # brand untouched


def test_register_undoes_a_small_shift():
    a = np.asarray(_ORIG)
    shifted = Image.fromarray(np.roll(a, (6, 9), axis=(0, 1)))
    back = np.asarray(compose.register(_ORIG, shifted)).astype(int)
    assert np.abs(back[20:-20, 20:-20] - a[20:-20, 20:-20].astype(int)).mean() < 4


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} branch tests passed.")
