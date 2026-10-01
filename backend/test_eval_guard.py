"""Tests for the reward-hack guard (eval_guard).

The guard is the second opinion that keeps the score honest: it rejects edits that
raise the *proxy* without a real on-target improvement. These pin the three cheats
it must catch, plus the case it must allow, then the rest-of-frame cheat (darken,
desaturate, blur or black out everything but the brand), calibrated on real recorded edits. numpy + Pillow only.

Run:  python -m pytest test_eval_guard.py   (or)   python test_eval_guard.py
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

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


# --- the rest-of-frame cheat: win by degrading everything outside the brand ---------
_BOX = [0.35, 0.35, 0.3, 0.3]  # normalized x, y, w, h
_PX = (70, 70, 130, 130)        # the same box in pixels on the 200x200 base


def _outside(fn) -> Image.Image:
    """Apply `fn` to the whole frame, then paste the untouched target back in."""
    out = fn(_BASE.copy())
    out.paste(_BASE.crop(_PX), _PX[:2])
    return out


def _gain_verdict(after: Image.Image) -> dict:
    # Every score signal says "win": share up AND absolute target salience up.
    return eval_guard.verdict(_BASE, after, ratio_before=0.4, ratio_after=0.6,
                              target_sal_before=0.20, target_sal_after=0.30, target_box=_BOX)


def test_darkening_the_rest_is_rejected():
    dark = _outside(lambda im: Image.fromarray((np.asarray(im) * 0.35).astype("uint8")))
    v = _gain_verdict(dark)
    assert v["decision"] == "reject"
    assert any("darkened" in r for r in v["reasons"])


def test_desaturating_the_rest_is_rejected():
    v = _gain_verdict(_outside(lambda im: im.convert("L").convert("RGB")))
    assert v["decision"] == "reject"
    assert any("desaturated" in r for r in v["reasons"])


def test_blurring_the_rest_is_rejected():
    v = _gain_verdict(_outside(lambda im: im.filter(ImageFilter.GaussianBlur(6))))
    assert v["decision"] == "reject"
    assert any("blurred" in r for r in v["reasons"])


def test_blacking_out_the_rest_is_rejected():
    v = _gain_verdict(_outside(lambda im: Image.new("RGB", im.size, (0, 0, 0))))
    assert v["decision"] == "reject"


def test_edit_inside_the_target_is_still_accepted():
    after = _BASE.copy()
    after.paste((255, 255, 255), (85, 85, 115, 115))  # a bright mark on the brand only
    assert _gain_verdict(after)["decision"] == "accept"


# --- calibration on real recorded edits (skipped if the files aren't there) ----------
_ROOT = Path(__file__).resolve().parents[1]
_PUB = _ROOT / "frontend" / "public"
_NIKE_BOX = [0.3, 0.18, 0.45, 0.3]


def test_june_nike_edit_is_rejected():
    """The old 59 -> 81 Nike 'win' muted everything except the billboard."""
    run = _PUB / "precomputed" / "nike.json"
    if not run.exists():
        return
    d = json.loads(run.read_text(encoding="utf-8"))
    img = lambda u: Image.open(io.BytesIO(base64.b64decode(u.split(",", 1)[-1]))).convert("RGB")
    oc = eval_guard.outside_change(img(d["original_png"]), img(d["variant_png"]), _NIKE_BOX)
    assert eval_guard.degradation(oc), oc


def test_recorded_honest_edits_pass_the_rest_of_frame_check():
    """Edits that changed the brand and left the scene alone must not trip the check."""
    cases = [("nike", "step3", _NIKE_BOX), ("spotify", "step1", [0.32, 0.28, 0.4, 0.5])]
    for sample, step, box in cases:
        after = _PUB / "replay" / sample / f"{step}.jpg"
        if not after.exists():
            continue
        before = Image.open(_PUB / "samples" / f"{sample}.jpg")
        oc = eval_guard.outside_change(before, Image.open(after), box)
        assert not eval_guard.degradation(oc), (sample, oc)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} guard tests passed.")
