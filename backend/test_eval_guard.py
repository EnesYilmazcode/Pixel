"""Tests for the reward-hack guard (eval_guard).

The guard is the second opinion that keeps the score honest: it rejects edits that
raise the *proxy* without a real on-target improvement. These pin the three cheats
it must catch, plus the case it must allow. numpy + Pillow only.

Run:  python -m pytest test_eval_guard.py   (or)   python test_eval_guard.py
"""
from __future__ import annotations

import numpy as np
from PIL import Image

import eval_guard

_RNG = np.random.default_rng(0)
_BASE = Image.fromarray(_RNG.integers(60, 180, (200, 200, 3)).astype("uint8"))


def _local_edit() -> Image.Image:
    """A clearly visible, localized change (bright box in a corner)."""
    img = _BASE.copy()
    img.paste((255, 255, 255), (150, 150, 195, 195))
    return img


def _global_shift() -> Image.Image:
    """A whole-frame brightness lift — the shape of a 'suppress everything else' cheat."""
    arr = np.asarray(_BASE).astype(np.int16)
    return Image.fromarray(np.clip(arr + 40, 0, 255).astype("uint8"))


def test_identical_is_rejected_imperceptible():
    v = eval_guard.verdict(_BASE, _BASE.copy(), ratio_before=0.4, ratio_after=0.5)
    assert v["decision"] == "reject"
    assert any("imperceptible" in r for r in v["reasons"])


def test_real_local_edit_with_abs_gain_is_accepted():
    v = eval_guard.verdict(
        _BASE, _local_edit(),
        ratio_before=0.4, ratio_after=0.5,
        target_sal_before=0.20, target_sal_after=0.30,
    )
    assert v["decision"] == "accept"


def test_suppression_is_rejected():
    """Share-on-target rose but the target's ABSOLUTE salience did not => suppression cheat."""
    v = eval_guard.verdict(
        _BASE, _global_shift(),
        ratio_before=0.4, ratio_after=0.5,
        target_sal_before=0.20, target_sal_after=0.20,  # flat absolute => cheat
    )
    assert v["decision"] == "reject"
    assert any("suppression" in r or "absolute salience" in r for r in v["reasons"])


def test_no_score_gain_is_rejected():
    v = eval_guard.verdict(
        _BASE, _local_edit(),
        ratio_before=0.5, ratio_after=0.5,  # no improvement
        target_sal_before=0.20, target_sal_after=0.25,
    )
    assert v["decision"] == "reject"
    assert any("did not improve" in r for r in v["reasons"])


def test_non_semantic_edit_is_rejected():
    v = eval_guard.verdict(
        _BASE, _local_edit(),
        ratio_before=0.4, ratio_after=0.5,
        target_sal_before=0.20, target_sal_after=0.30,
        edit_is_semantic=False,  # e.g. a no-op / unavailable edit
    )
    assert v["decision"] == "reject"


def test_perceptual_change_flags_global_vs_local():
    local = eval_guard.perceptual_change(_BASE, _local_edit())
    glob = eval_guard.perceptual_change(_BASE, _global_shift())
    assert local["perceptible"] and not local["is_global"]
    assert glob["is_global"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} guard tests passed.")
