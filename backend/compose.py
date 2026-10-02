"""Keep a generated edit only where it was meant to happen.

Nano Banana returns a whole new frame even for a one-object edit: it shifts the picture
by a few pixels, re-renders textures and nudges colors everywhere. On the recorded runs
that drift alone moved the score by a few points either way. So each branch edit is
registered back onto the original (translation only) and pasted in through a feathered
mask over the region the branch targets. Every pixel outside that region stays identical
to the original, and the score can only move because of the intended change.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REG_SIDE = 512      # register at this resolution
MAX_SHIFT = 0.05    # ignore a "registration" bigger than this fraction of the frame
GROW = 0.04         # grow the branch region by this fraction of the frame
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


def keep_region(orig: Image.Image, edited: Image.Image, regions) -> Image.Image:
    """The original, with the registered edit pasted in over `regions` only."""
    orig = orig.convert("RGB")
    if not regions:
        return orig
    return Image.composite(register(orig, edited), orig, region_mask(orig.size, regions))
