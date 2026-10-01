"""Reward-hacking guard for the optimize loop.  SELF-CONTAINED (numpy + Pillow only).

Why: the attention score is a *proxy*. An optimizer can raise it without improving
real attention — the classic cheats are (a) **suppression** (blur/darken/strip the
rest of the frame so the target's *share* rises while its own salience doesn't),
and (b) **imperceptible / global** tweaks the eye can't read as a design change.
This module gives the loop a cheap second opinion that catches those.

A third cheat is the one the absolute-salience check misses: darken, desaturate, blur
or black out everything except the brand. DeepGaze is a probability map, so pulling
mass off the rest of the frame raises the brand's absolute share too. Pass
`target_box` and the guard compares the rest of the frame before and after.

Wiring (Pixel): `deepgaze_runner.score_components(image, box)` returns both the
size-invariant prominence (the headline `ratio`) AND the absolute on-target salience
mass — feed both into `verdict(...)`:

    import eval_guard, deepgaze_runner as dg
    ratio_before, abs_before = dg.score_components(before_img, box)
    ratio_after,  abs_after  = dg.score_components(after_img,  box)
    v = eval_guard.verdict(
        before_img, after_img,
        ratio_before=ratio_before, ratio_after=ratio_after,
        target_sal_before=abs_before, target_sal_after=abs_after,
        edit_is_semantic=really_edited, target_box=box,
    )
    accepted = bool(v["decision"] == "accept")   # gate on this, surface v["reasons"]

It degrades gracefully: with no absolute-salience inputs it still runs the
perceptual + global-change checks. All thresholds are APPROXIMATE — calibrate on a
handful of your own "obviously visible" vs "invisible" edits.

The deepest fix is structural and lives in the loop, not here: **freeze the target
box at round 0** (never let the detector re-pick the target mid-optimization) and,
if you can, score with a 2nd saliency map and require agreement. See docs/EVAL_FLAWS.md.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

# --- thresholds (approximate; calibrate) ---
MAX_SIDE = 384          # downscale for speed
SSIM_FLOOR = 0.985      # mean SSIM above this => change effectively invisible -> reject
DIFF_THRESH = 8         # per-pixel abs diff (0..255) counted as "changed" (~JND noise floor)
GLOBAL_COVERAGE = 0.55  # fraction of pixels changed above which an edit looks "global"
GLOBAL_BBOX = 0.60      # change bounding-box covering more of the frame than this = "global"
EPS = 1e-4
GRID = 8                # cells per side for the rest-of-frame comparison
OUTSIDE_MARGIN = 0.04   # grow the target box by this before measuring "the rest of the frame"
# Floors for the rest of the frame, as after/before ratios. Below any of these, the edit
# raised the score by degrading everything that isn't the brand. Calibrated on the
# recorded edits in frontend/public/replay and results/ (see test_eval_guard.py).
OUTSIDE_FLOORS = {"lum": 0.80, "contrast": 0.75, "color": 0.70, "detail": 0.70}


def _gray(img: Image.Image, size=None) -> np.ndarray:
    """Grayscale float array, optionally resized to `size` (w, h)."""
    g = img.convert("L")
    if size is not None:
        g = g.resize(size, Image.BILINEAR)
    return np.asarray(g, dtype=np.float64)


def _fit(before: Image.Image, after: Image.Image):
    """Downscale both to a common size (after -> before's box), capped at MAX_SIDE."""
    w, h = before.size
    scale = min(1.0, MAX_SIDE / max(w, h))
    size = (max(8, int(w * scale)), max(8, int(h * scale)))
    return _gray(before, size), _gray(after, size)


def ssim_global(a: np.ndarray, b: np.ndarray, L: float = 255.0) -> float:
    """Whole-image SSIM — sensitive to global mean/variance shifts (good global detector)."""
    C1, C2 = (0.01 * L) ** 2, (0.03 * L) ** 2
    mx, my = a.mean(), b.mean()
    vx, vy = a.var(), b.var()
    cxy = ((a - mx) * (b - my)).mean()
    return float(((2 * mx * my + C1) * (2 * cxy + C2)) /
                 ((mx * mx + my * my + C1) * (vx + vy + C2)))


def _box_mean(img: np.ndarray, w: int) -> np.ndarray:
    """Mean over w*w windows via an integral image (O(N), no scipy)."""
    I = np.pad(img, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    s = I[w:, w:] - I[:-w, w:] - I[w:, :-w] + I[:-w, :-w]
    return s / (w * w)


def ssim_windowed(a: np.ndarray, b: np.ndarray, w: int = 7, L: float = 255.0) -> np.ndarray:
    """Per-window SSIM map — its low percentile reveals small *local* visible edits."""
    C1, C2 = (0.01 * L) ** 2, (0.03 * L) ** 2
    mx, my = _box_mean(a, w), _box_mean(b, w)
    vx = _box_mean(a * a, w) - mx * mx
    vy = _box_mean(b * b, w) - my * my
    vxy = _box_mean(a * b, w) - mx * my
    return ((2 * mx * my + C1) * (2 * vxy + C2)) / ((mx * mx + my * my + C1) * (vx + vy + C2))


def perceptual_change(before: Image.Image, after: Image.Image) -> dict:
    """Did a human-visible change happen, and is it localized or global?"""
    a, b = _fit(before, after)
    mean_ssim = ssim_global(a, b)
    wmap = ssim_windowed(a, b, w=7)
    p1_ssim = float(np.percentile(wmap, 1))  # worst local window (robust to single pixels)

    diff = np.abs(a - b)
    changed = diff > DIFF_THRESH
    coverage = float(changed.mean())
    ys, xs = np.where(changed)
    if xs.size:
        bbox_frac = ((ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)) / changed.size
    else:
        bbox_frac = 0.0

    perceptible = (mean_ssim < SSIM_FLOOR) or (p1_ssim < SSIM_FLOOR)
    is_global = (coverage > GLOBAL_COVERAGE) and (bbox_frac > GLOBAL_BBOX)
    return {
        "mean_ssim": round(mean_ssim, 4),
        "p1_ssim": round(p1_ssim, 4),
        "coverage": round(coverage, 4),
        "bbox_frac": round(bbox_frac, 4),
        "perceptible": bool(perceptible),
        "is_global": bool(is_global),
    }


def _rgb(img: Image.Image, size) -> np.ndarray:
    return np.asarray(img.convert("RGB").resize(size, Image.BILINEAR), dtype=np.float64)


def _outside_mask(h: int, w: int, box, margin: float = OUTSIDE_MARGIN) -> np.ndarray:
    """True outside the target box, grown by `margin` (fraction of the frame) on every side
    so a legit edit that spills slightly past the box isn't counted as 'the rest'."""
    x, y, bw, bh = box
    x0, y0 = int(max(0.0, x - margin) * w), int(max(0.0, y - margin) * h)
    x1, y1 = int(min(1.0, x + bw + margin) * w), int(min(1.0, y + bh + margin) * h)
    m = np.ones((h, w), bool)
    m[y0:y1, x0:x1] = False
    return m


def _stats(rgb: np.ndarray, mask: np.ndarray) -> dict:
    lum = rgb @ np.array([0.299, 0.587, 0.114])
    rg = rgb[..., 0] - rgb[..., 1]
    yb = 0.5 * (rgb[..., 0] + rgb[..., 1]) - rgb[..., 2]
    gy, gx = np.gradient(lum)
    grad = np.hypot(gx, gy)
    l, r, b = lum[mask], rg[mask], yb[mask]
    return {
        "lum": l.mean(),
        "contrast": l.std(),
        # Hasler & Suesstrunk colorfulness
        "color": np.hypot(r.std(), b.std()) + 0.3 * np.hypot(r.mean(), b.mean()),
        "detail": grad[mask].mean(),
    }


def outside_change(before: Image.Image, after: Image.Image, box) -> dict:
    """How the rest of the frame (outside the target) changed, as after/before ratios of
    luminance, luminance contrast, colorfulness and edge detail. Each ratio is the MEDIAN
    over a grid of cells, so removing one cluttering object (a few cells change) passes,
    while dimming, flattening, desaturating or blurring the whole scene (most cells
    change) does not. A ratio well below 1 means the edit degraded the rest of the frame."""
    w, h = before.size
    scale = min(1.0, MAX_SIDE / max(w, h))
    size = (max(8, int(w * scale)), max(8, int(h * scale)))
    a, b = _rgb(before, size), _rgb(after, size)
    mask = _outside_mask(size[1], size[0], box)
    ratios: dict[str, list[float]] = {"lum": [], "contrast": [], "color": [], "detail": []}
    ys = np.linspace(0, size[1], GRID + 1).astype(int)
    xs = np.linspace(0, size[0], GRID + 1).astype(int)
    for i in range(GRID):
        for j in range(GRID):
            cell = (slice(ys[i], ys[i + 1]), slice(xs[j], xs[j + 1]))
            m = mask[cell]
            if m.mean() < 0.5:  # mostly target; not "the rest of the frame"
                continue
            sa, sb = _stats(a[cell], m), _stats(b[cell], m)
            for k in ratios:
                ratios[k].append((sb[k] + 1.0) / (sa[k] + 1.0))
    if not ratios["lum"]:  # target fills the frame; nothing outside to judge
        return {k: 1.0 for k in ratios}
    return {k: round(float(np.median(v)), 3) for k, v in ratios.items()}


def degradation(oc: dict) -> list[str]:
    """Which of the rest-of-frame signals fell past its floor."""
    words = {"lum": "darkened", "contrast": "flattened", "color": "desaturated", "detail": "blurred"}
    return [f"{words[k]} ({oc[k]:.2f}x)" for k, floor in OUTSIDE_FLOORS.items() if oc[k] < floor]


def verdict(
    before: Image.Image,
    after: Image.Image,
    *,
    ratio_before: float,
    ratio_after: float,
    target_sal_before: float | None = None,
    target_sal_after: float | None = None,
    sal2_before: float | None = None,
    sal2_after: float | None = None,
    edit_is_semantic: bool = True,
    target_box=None,
) -> dict:
    """Decide accept / reject / review for one edit. Gate `accepted` on decision == 'accept'.

    Priority of checks (reasons explain every outcome):
      0. rest of frame degraded   -> reject  (score rose, but the frame outside the target got
                                              darker / flatter / grayer / blurrier; needs `target_box`)
      1. imperceptible            -> reject (invisible tweak / adversarial)
      2. score didn't improve     -> reject
      3. suppression hack         -> reject  (share up but absolute target salience flat/down)
      4. absolute target flat     -> reject  (nothing actually got more salient)
      5. two models disagree      -> review  (possible single-model artifact)
      6. global change unconfirmed -> review (can't tell a real big edit from a global cheat)
      7. else                     -> accept
    """
    pc = perceptual_change(before, after)
    reasons: list[str] = []
    ratio_gain = (ratio_after - ratio_before) > EPS
    have_abs = target_sal_before is not None and target_sal_after is not None
    real_gain = have_abs and (target_sal_after - target_sal_before) > EPS
    suppression = have_abs and ratio_gain and not real_gain
    have_2 = sal2_before is not None and sal2_after is not None
    models_agree = (not have_2) or (
        ((target_sal_after or ratio_after) - (target_sal_before or ratio_before) > 0)
        == ((sal2_after - sal2_before) > 0)
    )

    oc = outside_change(before, after, target_box) if target_box is not None else None

    def out(decision: str) -> dict:
        return {"decision": decision, "reasons": reasons, **pc, "outside": oc,
                "ratio_gain": round(ratio_after - ratio_before, 4),
                "abs_gain": round((target_sal_after - target_sal_before), 4) if have_abs else None}

    # First, because SSIM runs on luminance and can't see a pure desaturation.
    if ratio_gain and oc is not None and degradation(oc):
        reasons.append("raised the score by degrading the rest of the frame: " + ", ".join(degradation(oc)))
        return out("reject")
    if not pc["perceptible"]:
        reasons.append(f"change is imperceptible (ssim {pc['mean_ssim']}/{pc['p1_ssim']}) — likely reward-hack")
        return out("reject")
    if not ratio_gain:
        reasons.append("attention score did not improve")
        return out("reject")
    if suppression:
        reasons.append("share-on-target rose but the target's own salience did not — suppression cheat (blur/strip rest)")
        return out("reject")
    if have_abs and not real_gain:
        reasons.append("target's absolute salience did not rise")
        return out("reject")
    if not edit_is_semantic:
        reasons.append("not a real content edit")
        return out("reject")
    if not models_agree:
        reasons.append("two saliency signals disagree — possible single-model artifact; confirm visually")
        return out("review")
    if pc["is_global"] and not real_gain:
        reasons.append("change covers most of the frame and no absolute-salience confirmation — confirm it's a real edit, not a global filter")
        return out("review")
    reasons.append("perceptible, localized/justified, and target salience improved")
    return out("accept")


if __name__ == "__main__":  # smoke test — `python eval_guard.py`
    import numpy as _np
    base = Image.fromarray((_np.random.default_rng(0).integers(60, 180, (200, 200, 3))).astype("uint8"))
    same = base.copy()
    local = base.copy(); local.paste((255, 255, 255), (150, 150, 195, 195))  # bright corner box
    arr = _np.asarray(base).astype(_np.int16); glob = Image.fromarray(_np.clip(arr + 40, 0, 255).astype("uint8"))

    print("identical          ->", verdict(base, same, ratio_before=.4, ratio_after=.5)["decision"], "(want reject: imperceptible)")
    print("local + abs up     ->", verdict(base, local, ratio_before=.4, ratio_after=.5,
          target_sal_before=.20, target_sal_after=.30)["decision"], "(want accept)")
    print("global, abs flat   ->", verdict(base, glob, ratio_before=.4, ratio_after=.5,
          target_sal_before=.20, target_sal_after=.20)["decision"], "(want reject: suppression)")
