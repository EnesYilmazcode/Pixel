"""Reward-hacking guard for the optimize loop.  SELF-CONTAINED (numpy + Pillow only).

Why: the attention score is a *proxy*. An optimizer can raise it without improving
real attention — the classic cheats are (a) **suppression** (blur/darken/strip the
rest of the frame so the target's *share* rises while its own salience doesn't),
and (b) **imperceptible / global** tweaks the eye can't read as a design change.
This module gives the loop a cheap second opinion that catches those.

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
        edit_is_semantic=really_edited,
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
) -> dict:
    """Decide accept / reject / review for one edit. Gate `accepted` on decision == 'accept'.

    Priority of checks (reasons explain every outcome):
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

    def out(decision: str) -> dict:
        return {"decision": decision, "reasons": reasons, **pc,
                "ratio_gain": round(ratio_after - ratio_before, 4),
                "abs_gain": round((target_sal_after - target_sal_before), 4) if have_abs else None}

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
