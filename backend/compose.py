"""Keep a generated edit only where it was meant to happen.

Nano Banana returns a whole new frame even for a one-object edit: it shifts the picture
by a few pixels, re-renders textures and nudges colors everywhere. On the recorded runs
that drift alone moved the score by a few points either way. So each branch edit is
registered back onto the original (translation only), and only the pixels that really
changed near the branch's target are pasted in. A fixed box around the thief was not
enough: it cut objects in half and left seams, so the mask follows the actual change.
Every other pixel stays identical to the original.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import binary_dilation, binary_fill_holes, binary_opening, gaussian_filter

REG_SIDE = 512      # register at this resolution
MAX_SHIFT = 0.05    # ignore a "registration" bigger than this fraction of the frame
GROW = 0.04         # grow the branch region by this fraction of the frame
NEAR = 0.08         # a changed pixel counts only within this distance of the branch region
DIFF_SIDE = 256     # resolution of the change map
DIFF_THRESH = 24    # mean RGB difference (0..255) that counts as a real change
FEATHER = 0.012     # feather radius, fraction of the long side


def _gray(img: Image.Image, size) -> np.ndarray:
    return np.asarray(img.convert("L").resize(size, Image.BILINEAR), dtype=np.float64)


def estimate_shift(orig: Image.Image, edited: Image.Image) -> tuple[float, float]:
    """(dx, dy) in original pixels such that edited(x + dx, y + dy) ~ orig(x, y),
    by phase correlation. Returns (0, 0) when the peak is implausibly far."""
    w, h = orig.size
    s = REG_SIDE / max(w, h)
    size = (max(16, int(w * s)), max(16, int(h * s)))
    a, b = _gray(orig, size), _gray(edited, size)
    win = np.outer(np.hanning(size[1]), np.hanning(size[0]))
    fa, fb = np.fft.fft2((a - a.mean()) * win), np.fft.fft2((b - b.mean()) * win)
    r = fb * np.conj(fa)
    corr = np.fft.ifft2(r / (np.abs(r) + 1e-9)).real
    dy, dx = np.unravel_index(int(corr.argmax()), corr.shape)
    if dy > size[1] // 2:
        dy -= size[1]
    if dx > size[0] // 2:
        dx -= size[0]
    if abs(dx) > MAX_SHIFT * size[0] or abs(dy) > MAX_SHIFT * size[1]:
        return 0.0, 0.0
    return dx / s, dy / s


def register(orig: Image.Image, edited: Image.Image) -> Image.Image:
    """Shift `edited` so it lines up with `orig`."""
    edited = edited.convert("RGB").resize(orig.size, Image.LANCZOS)
    dx, dy = estimate_shift(orig, edited)
    if dx == 0 and dy == 0:
        return edited
    return edited.transform(orig.size, Image.AFFINE, (1, 0, dx, 0, 1, dy), resample=Image.BILINEAR)


def region_mask(size, regions, grow: float = GROW, feather: float = FEATHER) -> Image.Image:
    """Feathered mask covering the normalized [x, y, w, h] regions, each grown by `grow`."""
    w, h = size
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    for x, y, bw, bh in regions:
        d.rectangle([(x - grow) * w, (y - grow) * h, (x + bw + grow) * w, (y + bh + grow) * h], fill=255)
    return m.filter(ImageFilter.GaussianBlur(feather * max(w, h)))


def change_mask(orig: Image.Image, edited: Image.Image, near, protect=None) -> Image.Image:
    """Feathered mask of where `edited` really differs from `orig`: blurred at low
    resolution so jitter drops out, limited to within NEAR of the `near` regions, and
    never inside the `protect` regions (the brand's own box)."""
    w, h = orig.size
    s = DIFF_SIDE / max(w, h)
    size = (max(16, int(w * s)), max(16, int(h * s)))
    a = np.asarray(orig.convert("RGB").resize(size, Image.BILINEAR), np.float64)
    b = np.asarray(edited.convert("RGB").resize(size, Image.BILINEAR), np.float64)
    m = gaussian_filter(np.abs(a - b).mean(2), 1.5) > DIFF_THRESH
    m = binary_opening(m, iterations=1)
    m = binary_fill_holes(binary_dilation(m, iterations=3))
    allow = np.asarray(region_mask(size, near, grow=NEAR, feather=0)) > 0
    if protect:
        allow &= ~(np.asarray(region_mask(size, protect, grow=0.0, feather=0)) > 0)
    m &= allow
    mi = Image.fromarray((m * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
    return mi.filter(ImageFilter.GaussianBlur(FEATHER * max(w, h)))


def keep_changes(orig: Image.Image, edited: Image.Image, near, protect=None) -> Image.Image:
    """The original, with only the real changes of the registered edit near `near` pasted in."""
    orig = orig.convert("RGB")
    reg = register(orig, edited)
    return Image.composite(reg, orig, change_mask(orig, reg, near, protect))
