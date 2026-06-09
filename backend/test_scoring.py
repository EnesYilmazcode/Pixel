"""Tests for the honest scoring metric (deepgaze_runner).

These pin the properties that make the attention number trustworthy and run with
just numpy + Pillow (no torch / no model weights), so they're fast and CI-safe:

  - size-invariance: the score is NOT inflated by simply making the target bigger,
  - dimension-invariance: the same content scores the same at any grid resolution,
  - calibration: a uniform attention field reads ~0.5 (exactly "average") for any box,
  - direction: concentrated on-target mass scores high; off-target mass scores low,
  - range: the score is always in [0, 1].

Run:  python -m pytest test_scoring.py   (or)   python test_scoring.py
"""
from __future__ import annotations

import numpy as np
from PIL import Image

import deepgaze_runner as dg


def _uniform(h: int, w: int) -> np.ndarray:
    d = np.ones((h, w), dtype=np.float64)
    return d / d.sum()


def _blob(h: int, w: int, cx: float, cy: float, sigma: float) -> np.ndarray:
    """A single Gaussian attention blob centered at normalized (cx, cy)."""
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.exp(-(((xx - cx * w) ** 2 + (yy - cy * h) ** 2) / (2 * (sigma * max(h, w)) ** 2)))
    return d / d.sum()


def test_uniform_is_half_for_any_box():
    """A flat attention field => prominence 0.5 (exactly average) for ANY box."""
    d = _uniform(120, 160)
    for box in ([0.1, 0.1, 0.2, 0.2], [0.0, 0.0, 0.9, 0.9], [0.4, 0.4, 0.1, 0.1]):
        assert abs(dg.prominence(d, box) - 0.5) < 0.01, box


def test_size_invariant_not_inflated_by_bigger_box():
    """Growing the box over EMPTY area must not raise prominence — it should fall.
    (Raw mass-in-box would rise; the size-invariant metric must not reward size.)"""
    d = _blob(120, 160, cx=0.5, cy=0.5, sigma=0.06)
    tight = dg.prominence(d, [0.44, 0.44, 0.12, 0.12])     # snug on the blob
    loose = dg.prominence(d, [0.20, 0.20, 0.60, 0.60])     # same blob + lots of empty area
    assert tight > loose, (tight, loose)
    assert tight > 0.5 > 0.0


def test_dimension_invariance():
    """The same content at two grid resolutions scores within rounding of each other."""
    box = [0.4, 0.4, 0.2, 0.2]
    small = dg.prominence(_blob(90, 120, 0.5, 0.5, 0.07), box)
    big = dg.prominence(_blob(360, 480, 0.5, 0.5, 0.07), box)
    assert abs(small - big) < 0.03, (small, big)


def test_off_target_scores_low():
    """Mass concentrated OUTSIDE the box => the box under-pulls => prominence < 0.5."""
    d = _blob(120, 160, cx=0.85, cy=0.15, sigma=0.05)      # top-right blob
    on_blob = dg.prominence(d, [0.78, 0.08, 0.16, 0.16])
    off_blob = dg.prominence(d, [0.05, 0.70, 0.20, 0.20])  # bottom-left, empty
    assert on_blob > 0.5 > off_blob, (on_blob, off_blob)


def test_score_in_range():
    for d in (_uniform(50, 50), _blob(80, 80, 0.5, 0.5, 0.03), _blob(80, 80, 0.1, 0.1, 0.2)):
        for box in ([0.0, 0.0, 1.0, 1.0], [0.3, 0.3, 0.3, 0.3], [0.45, 0.45, 0.05, 0.05]):
            s = dg.prominence(d, box)
            assert 0.0 <= s <= 1.0, (s, box)


def test_degenerate_box_is_zero():
    d = _uniform(40, 40)
    assert dg.prominence(d, [0.5, 0.5, 0.0, 0.0]) == 0.0
    assert dg.prominence(d, [1.5, 1.5, 0.1, 0.1]) == 0.0  # off-image


def test_absolute_mass_grows_with_box_but_prominence_does_not():
    """Sanity: attention_in_box (absolute) is the raw mass and DOES grow with box size,
    which is exactly why it's not the headline score — prominence divides it out."""
    d = _blob(120, 160, 0.5, 0.5, 0.2)  # broad blob so a bigger box captures more mass
    small_mass = dg.attention_in_box(d, [0.45, 0.45, 0.10, 0.10])
    big_mass = dg.attention_in_box(d, [0.20, 0.20, 0.60, 0.60])
    assert big_mass > small_mass  # absolute mass rises with size...
    # ...but prominence should not be higher for the bigger, area-diluted box.
    assert dg.prominence(d, [0.20, 0.20, 0.60, 0.60]) <= dg.prominence(d, [0.45, 0.45, 0.10, 0.10]) + 1e-6


def test_align_to_input_fixes_dimensions():
    """Before/after must be comparable: an edit is forced back to the input WxH."""
    edited = Image.new("RGB", (300, 200), (10, 20, 30))
    out = dg.align_to_input(edited, 256, 256)
    assert out.size == (256, 256)


def test_integrity_ok_rejects_aspect_change():
    assert dg.integrity_ok(100, 100, 100, 100) is True
    assert dg.integrity_ok(100, 100, 200, 100) is False  # aspect ratio changed a lot


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} scoring tests passed.")
