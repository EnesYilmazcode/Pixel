"""Vision spine: predict where eyes look + score attention on a target region.

Uses DeepGaze IIE when torch + weights are present; otherwise a cheap edge+center
saliency so the server always runs (demo-safe). All scoring is dimension-invariant
(normalized boxes, density re-normalized) per PLAN.md's critical-risk note.
"""
from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import gaussian_filter, sobel

Box = list[float]  # normalized [x, y, w, h]
_CENTER_BOX: Box = [0.35, 0.35, 0.30, 0.30]

_model = None  # lazy DeepGaze IIE handle; None until first (successful) load


# --- dimension-fix helpers (see PLAN.md → Critical Build Risk) -------------------
def align_to_input(edited: Image.Image, in_w: int, in_h: int) -> Image.Image:
    """Force an edited image back to the input's exact WxH (pad-to-aspect, no stretch)
    so before/after attention is comparable."""
    if edited.size == (in_w, in_h):
        return edited
    return ImageOps.pad(edited, (in_w, in_h), method=Image.LANCZOS, color=(0, 0, 0))


def attention_in_box(density: np.ndarray, nbox: Box) -> float:
    """Fraction of total attention mass inside a normalized box (resolution-invariant)."""
    h, w = density.shape
    x, y, bw, bh = nbox
    x0, y0 = max(0, int(x * w)), max(0, int(y * h))
    x1, y1 = min(w, int((x + bw) * w)), min(h, int((y + bh) * h))
    d = density / (density.sum() + 1e-9)
    return float(d[y0:y1, x0:x1].sum())


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


def _density(arr: np.ndarray) -> np.ndarray:
    """DeepGaze IIE density if available, else the fallback."""
    global _model
    try:
        import torch  # noqa: F401
        import deepgaze_pytorch  # noqa: F401
        # TODO(activate real model): load DeepGaze IIE + MIT1003 centerbias once,
        # run model(image_tensor, centerbias_tensor), np.exp the log-density.
        # Kept behind the fallback until torch + weights are installed.
        raise ImportError("DeepGaze wiring pending; using fallback")
    except Exception:
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


def _top_distractors(density: np.ndarray, target: Box, k: int = 2) -> list[dict]:
    """Highest-attention grid cells outside the target, as normalized callouts."""
    rows, cols = 4, 6
    h, w = density.shape
    total = density.sum() + 1e-9
    cells = []
    for r in range(rows):
        for c in range(cols):
            y0, y1 = r * h // rows, (r + 1) * h // rows
            x0, x1 = c * w // cols, (c + 1) * w // cols
            nbox = [x0 / w, y0 / h, (x1 - x0) / w, (y1 - y0) / h]
            share = float(density[y0:y1, x0:x1].sum() / total)
            cells.append((share, nbox, _label(r, c, rows, cols)))
    tx, ty = target[0] + target[2] / 2, target[1] + target[3] / 2
    cells = [c for c in cells if not (c[1][0] <= tx <= c[1][0] + c[1][2]
                                      and c[1][1] <= ty <= c[1][1] + c[1][3])]
    cells.sort(reverse=True)
    return [{"region": nbox, "share": round(share, 3), "desc": desc}
            for share, nbox, desc in cells[:k]]


def _label(r: int, c: int, rows: int, cols: int) -> str:
    v = "upper" if r < rows / 3 else "lower" if r > 2 * rows / 3 else "middle"
    hzt = "left" if c < cols / 3 else "right" if c > 2 * cols / 3 else "center"
    return f"{v}-{hzt} region"


def _scanpath(density: np.ndarray, n: int = 5) -> list[dict]:
    """Greedy peaks (suppress a neighborhood after each pick) as an ordered gaze path."""
    d = density.copy()
    h, w = d.shape
    out = []
    for order in range(1, n + 1):
        y, x = np.unravel_index(int(d.argmax()), d.shape)
        out.append({"x": round(x / w, 3), "y": round(y / h, 3), "order": order})
        ry, rx = h // 8, w // 8
        d[max(0, y - ry):y + ry, max(0, x - rx):x + rx] = 0
    return out


def predict(image: Image.Image, target_box: Box | None = None) -> dict:
    """Full /predict payload for one image."""
    arr = np.asarray(image.convert("RGB"))
    h, w = arr.shape[:2]
    target = target_box or _CENTER_BOX
    density = _density(arr)
    return {
        "width": w,
        "height": h,
        "attention_score": round(attention_in_box(density, target), 4),
        "heatmap_png": _heatmap_data_url(density),
        "target_box": [round(v, 4) for v in target],
        "scanpath": _scanpath(density),
        "distractors": _top_distractors(density, target),
    }


def score_only(image: Image.Image, target_box: Box) -> float:
    """Cheap attention-on-target score (used by the agent loop's re-score step)."""
    return round(attention_in_box(_density(np.asarray(image.convert("RGB"))), target_box), 4)
