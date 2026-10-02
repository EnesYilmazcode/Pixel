"""Tests for the branch edits and for keeping each edit inside its region.

Run:  python -m pytest test_branches.py   (or)   python test_branches.py
"""
from __future__ import annotations

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


def test_no_branch_adds_text_or_dims_the_scene():
    banned = ("headline", "call-to-action", "cta", "slogan", "wordmark", "dim", "darken",
              "tone down", "desaturate", "blur")
    for b in branches(_BEFORE, "Nike"):
        assert not any(w in b["directive"].lower() for w in banned), b["directive"]


def test_ad_with_no_thieves_still_gets_a_branch():
    assert len(branches({"target_box": [0.3, 0.3, 0.3, 0.3], "distractors": []}, "Pepsi")) == 1


def test_keep_region_leaves_everything_else_identical():
    edited = Image.new("RGB", _ORIG.size, (255, 0, 0))  # the model redrew the whole frame
    region = [0.1, 0.1, 0.2, 0.2]
    out = np.asarray(compose.keep_region(_ORIG, edited, [region])).astype(int)
    a = np.asarray(_ORIG).astype(int)
    m = np.asarray(compose.region_mask(_ORIG.size, [region])) == 0
    assert (out[m] == a[m]).all()                      # untouched pixels stay identical
    assert out[45, 30, 0] > 200 and out[45, 30, 1] < 60  # the region itself took the edit


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
