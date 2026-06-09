"""Vision spine: predict where eyes look + score attention on a target region.

Uses DeepGaze IIE when torch + weights are present; otherwise a cheap edge+center
saliency so the server always runs (demo-safe). The fallback is NOT silent: /health
and the mode badge report which engine actually ran (see model_loaded/engine_name).

The headline number is a **size-invariant brand-prominence** score, not raw
mass-in-box: ratio = (attention mass inside the box) / (box's area fraction), then
score = ratio / (ratio + 1). So 0.5 = the region is exactly average salience for its
size, >0.5 = it out-pulls its size. This is deliberate — a raw mass fraction rewards
simply making the target physically bigger (a tiny logo is stuck near 0 no matter how
eye-catching), which measures "did you enlarge it" instead of "is it more prominent."
The size-invariant score moves when composition/contrast/clutter change, not just size.

Public surface (consumed by main.py / agents.py / gemini.py — keep stable):
    predict(image, target_box=None) -> dict        full /predict payload
    score_only(image, target_box) -> float         cheap re-score for the agent loop
    score_components(image, target_box) -> (prom, abs_mass)  prominence + absolute salience
    to_data_url(image) -> str                       PNG data URL for variants
    align_to_input(edited, in_w, in_h) -> Image     dimension-fix for before/after
    attention_in_box(density, nbox) -> float        absolute attention mass in a box
    prominence(density, nbox) -> float              size-invariant brand prominence
    integrity_ok(...) -> bool
    model_loaded() / engine_name() / device_name()  honest engine reporting for /health
"""
from __future__ import annotations

import base64
import io
import os

import numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import gaussian_filter, sobel

Box = list[float]  # normalized [x, y, w, h]
_CENTER_BOX: Box = [0.35, 0.35, 0.30, 0.30]

_model = None    # lazy DeepGaze IIE handle; None until first (successful) load
_device = None   # torch device once the model loads
_MODEL_MAX = 1024  # downscale long side before the model (CPU speed; scoring is normalized)

# Which engine produced the LAST density. Reported by /health so a fallback run can
# never silently pose as the real model. "uninitialized" until the first predict.
_engine = "uninitialized"


def model_loaded() -> bool:
    """True only when the REAL DeepGaze model produced the last density (honest /health)."""
    return _engine == "deepgaze-iie"


def engine_name() -> str:
    """Which saliency engine produced the last prediction (drives the LIVE/DEMO badge)."""
    return _engine


def device_name() -> str | None:
    """torch device the model loaded on ('cpu'/'cuda'), or None if it never loaded."""
    return _device


# --- dimension-fix helpers (see PLAN.md → Critical Build Risk) -------------------
def align_to_input(edited: Image.Image, in_w: int, in_h: int) -> Image.Image:
    """Force an edited image back to the input's exact WxH (pad-to-aspect, no stretch)
    so before/after attention is comparable."""
    if edited.size == (in_w, in_h):
        return edited
    return ImageOps.pad(edited, (in_w, in_h), method=Image.LANCZOS, color=(0, 0, 0))


def _box_px(density: np.ndarray, nbox: Box):
    """Clip a normalized box to integer pixel coords on the density grid.
    Returns (x0, y0, x1, y1, h, w) — shared by attention_in_box and prominence so the
    mass and the area fraction are computed over the EXACT same region."""
    h, w = density.shape
    x, y, bw, bh = nbox
    x0, y0 = max(0, int(x * w)), max(0, int(y * h))
    x1, y1 = min(w, int((x + bw) * w)), min(h, int((y + bh) * h))
    return x0, y0, x1, y1, h, w


def attention_in_box(density: np.ndarray, nbox: Box) -> float:
    """Absolute attention mass inside a normalized box: the fraction of total predicted
    attention that falls in the box (resolution-invariant). This is the RAW mass — it
    grows as the box grows, so it's used for distractor shares and as the eval_guard's
    'absolute on-target salience', NOT as the headline score (see prominence)."""
    x0, y0, x1, y1, _, _ = _box_px(density, nbox)
    d = density / (density.sum() + 1e-9)
    return float(d[y0:y1, x0:x1].sum())


def prominence(density: np.ndarray, nbox: Box) -> float:
    """Size-invariant brand prominence — the honest headline score.

    ratio = (attention mass inside the box) / (box's area fraction);  score = ratio/(ratio+1).
    So 0.5 = the region is exactly average salience for its size, >0.5 = it out-pulls its
    size, <0.5 = it under-pulls. Unlike raw mass-in-box, this does NOT reward simply making
    the target bigger (a tiny but eye-catching logo can score high), so optimization is
    pushed toward composition/contrast/clutter changes rather than just enlarging the target."""
    x0, y0, x1, y1, h, w = _box_px(density, nbox)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inside = attention_in_box(density, nbox)
    area_frac = ((x1 - x0) * (y1 - y0)) / float(h * w)
    ratio = inside / max(area_frac, 1e-6)
    return float(ratio / (ratio + 1.0))


def integrity_ok(in_w: int, in_h: int, out_w: int, out_h: int,
                 target_relocated: bool = True, ar_tol: float = 0.06) -> bool:
    """Reject a degenerate edit before trusting its score."""
    in_ar, out_ar = in_w / in_h, out_w / out_h
    if abs(in_ar - out_ar) / in_ar > ar_tol:
        return False
    return target_relocated


# --- saliency ---------------------------------------------------------------------
def _fallback_density(arr: np.ndarray) -> np.ndarray:
    """Edge energy * center bias, blurred and normalized. A stand-in for DeepGaze."""
    gray = arr.mean(axis=2)
    edges = np.hypot(sobel(gray, axis=0), sobel(gray, axis=1))
    edges = gaussian_filter(edges, sigma=max(gray.shape) / 60.0)
    edges /= edges.max() + 1e-9

    h, w = gray.shape
    yy, xx = np.mgrid[0:h, 0:w]
    cb = np.exp(-(((xx - w / 2) / (w * 0.45)) ** 2 + ((yy - h / 2) / (h * 0.45)) ** 2))

    d = (0.7 * edges + 0.3) * cb
    return d / (d.sum() + 1e-9)


def _centerbias(h: int, w: int) -> np.ndarray:
    """Flat (uniform) log-density centerbias. DeepGaze requires a centerbias input; a
    flat one keeps the prediction CONTENT-driven instead of baking in a 'stuff near the
    center wins' prior. That matters for honest scoring: with a strong center prior the
    attention-on-target number barely moves when you declutter or suppress a distractor
    (the prior masks the change), and off-center targets are unfairly penalized. Flat =
    the score reflects where the image content actually draws the eye."""
    from scipy.special import logsumexp
    cb = np.zeros((h, w), dtype=np.float64)
    return cb - logsumexp(cb)


def _density(arr: np.ndarray) -> np.ndarray:
    """DeepGaze IIE density if torch + weights are available, else the fallback.
    Records which engine ran in `_engine` so /health never reports a fallback as real."""
    global _model, _device, _engine
    try:
        import torch
        import deepgaze_pytorch

        if _model is None:
            _device = "cuda" if torch.cuda.is_available() else "cpu"
            _model = deepgaze_pytorch.DeepGazeIIE(pretrained=True).to(_device).eval()

        h, w = arr.shape[:2]
        scale = _MODEL_MAX / max(h, w) if max(h, w) > _MODEL_MAX else 1.0
        small = (np.asarray(Image.fromarray(arr).resize(
            (max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS))
            if scale < 1.0 else arr)

        sh, sw = small.shape[:2]
        img_t = torch.tensor(small.transpose(2, 0, 1)[None]).float().to(_device)
        cb_t = torch.tensor(_centerbias(sh, sw)[None]).float().to(_device)
        with torch.no_grad():
            log_density = _model(img_t, cb_t)
        d = np.exp(log_density[0, 0].cpu().numpy())
        _engine = "deepgaze-iie"
        return d / (d.sum() + 1e-9)
    except Exception:
        _engine = "edge+center fallback"
        return _fallback_density(arr)


# --- rendering / features ---------------------------------------------------------
def _heatmap_data_url(density: np.ndarray) -> str:
    d = density / (density.max() + 1e-9)
    a = (d ** 0.7 * 220).astype(np.uint8)
    rgba = np.zeros((*d.shape, 4), np.uint8)
    rgba[..., 0] = 255                       # red channel
    rgba[..., 1] = (d * 180).astype(np.uint8)  # toward yellow at peaks
    rgba[..., 3] = a
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def to_data_url(image: Image.Image) -> str:
    """PNG data URL for any PIL image (used for /edit variants + before/after frames)."""
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _label(ny: float, nx: float) -> str:
    """Human-readable position of a normalized point, for demo callouts."""
    vert = "upper" if ny < 1 / 3 else "lower" if ny > 2 / 3 else "middle"
    horz = "left" if nx < 1 / 3 else "right" if nx > 2 / 3 else "center"
    return f"{vert}-{horz} region"


def _top_distractors(density: np.ndarray, target: Box, k: int = 2,
                     sigma_frac: float = 0.10) -> list[dict]:
    """Highest-attention peaks OUTSIDE the target, localized precisely via greedy
    peak-pick with Gaussian inhibition-of-return, then labelled by position."""
    h, w = density.shape
    d = density.astype(np.float64).copy()
    sigma = sigma_frac * max(h, w)
    half = sigma_frac  # half-extent of the reported region, normalized
    yy, xx = np.ogrid[:h, :w]
    tx, ty, tw, th = target
    out: list[dict] = []
    for _ in range(k + 4):  # over-sample, then drop peaks that fall inside the target
        y, x = np.unravel_index(int(d.argmax()), d.shape)
        nx, ny = x / w, y / h
        region = [round(max(0.0, nx - half), 4), round(max(0.0, ny - half), 4),
                  round(min(1.0, 2 * half), 4), round(min(1.0, 2 * half), 4)]
        share = round(attention_in_box(density, region), 3)
        inside = (tx <= nx <= tx + tw) and (ty <= ny <= ty + th)
        if not inside and share > 0.02:
            out.append({"region": region, "share": share, "desc": _label(ny, nx)})
        d = np.clip(d - d[y, x] * np.exp(-(((xx - x) ** 2 + (yy - y) ** 2) / (2 * sigma ** 2))), 0, None)
        if len(out) >= k:
            break
    return out


def _scanpath(density: np.ndarray, n: int = 5, sigma_frac: float = 0.08) -> list[dict]:
    """Ordered fixation nodes: greedy peaks with Gaussian inhibition-of-return — a
    near-free stand-in for DeepGaze III scanpath that spreads nodes naturally."""
    h, w = density.shape
    d = density.astype(np.float64).copy()
    sigma = sigma_frac * max(h, w)
    yy, xx = np.ogrid[:h, :w]
    out = []
    for order in range(1, n + 1):
        y, x = np.unravel_index(int(d.argmax()), d.shape)
        out.append({"x": round(x / w, 3), "y": round(y / h, 3), "order": order})
        d = np.clip(d - d[y, x] * np.exp(-(((xx - x) ** 2 + (yy - y) ** 2) / (2 * sigma ** 2))), 0, None)
    return out


def predict(image: Image.Image, target_box: Box | None = None) -> dict:
    """Full /predict payload for one image. `attention_score` is the size-invariant
    prominence; `target_salience` is the absolute attention mass on target (used by the
    reward-hack guard to tell a real improvement from 'suppress everything else')."""
    arr = np.asarray(image.convert("RGB"))
    h, w = arr.shape[:2]
    target = target_box or _CENTER_BOX
    density = _density(arr)
    return {
        "width": w,
        "height": h,
        "attention_score": round(prominence(density, target), 4),
        "target_salience": round(attention_in_box(density, target), 4),
        "heatmap_png": _heatmap_data_url(density),
        "target_box": [round(v, 4) for v in target],
        "scanpath": _scanpath(density),
        "distractors": _top_distractors(density, target),
        "engine": _engine,
    }


def score_only(image: Image.Image, target_box: Box) -> float:
    """Cheap size-invariant prominence score (used by the agent loop's re-score step)."""
    return round(prominence(_density(np.asarray(image.convert("RGB"))), target_box), 4)


def score_components(image: Image.Image, target_box: Box) -> tuple[float, float]:
    """Both axes in a single density pass: (size-invariant prominence, absolute on-target
    salience mass). The guard needs the absolute mass to catch 'win by suppression'."""
    d = _density(np.asarray(image.convert("RGB")))
    return round(prominence(d, target_box), 4), round(attention_in_box(d, target_box), 4)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        img = Image.open(sys.argv[1]).convert("RGB")
    else:  # synthetic image so the pipeline can be smoke-tested without assets
        arr = np.zeros((480, 640, 3), np.uint8)
        arr[120:260, 380:560] = (220, 40, 40)  # a bright "product" block
        img = Image.fromarray(arr)

    rep = predict(img, [0.6, 0.25, 0.3, 0.3])
    in_range = 0 <= rep["attention_score"] <= 1
    print(f"engine={rep['engine']} size={rep['width']}x{rep['height']} "
          f"prominence={rep['attention_score']} abs_salience={rep['target_salience']} in[0,1]={in_range}")
    print(f"scanpath nodes={len(rep['scanpath'])} distractors={len(rep['distractors'])}")
    print(f"heatmap data-url ok={rep['heatmap_png'].startswith('data:image/png;base64,')}")

    # Size-invariance sanity: a uniform density must read ~0.5 prominence for ANY box size.
    uni = np.ones((100, 100)) / 10000
    small_p = round(prominence(uni, [0.1, 0.1, 0.2, 0.2]), 3)
    big_p = round(prominence(uni, [0.0, 0.0, 0.9, 0.9]), 3)
    print(f"uniform prominence small={small_p} big={big_p} (both want ~0.5)")
    assert abs(small_p - 0.5) < 0.02 and abs(big_p - 0.5) < 0.02, "prominence not size-invariant!"
    print("OK - size-invariant, content-driven prominence.")
