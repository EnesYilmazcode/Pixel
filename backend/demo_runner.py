"""Demo harness: run the full optimize loop on real sample ads and save before/after
visuals so the result can be eyeballed for a live demo.

Usage (from backend/, venv active):
    python demo_runner.py                 # default brands
    python demo_runner.py nike red-bull   # specific samples

For each brand it writes to backend/demo_out/<brand>/:
    before.png            the original ad
    after.png             the winning optimized variant
    heatmap_before.png    DeepGaze attention on the original
    heatmap_after.png     DeepGaze attention on the winner
    compare.png           side-by-side before|after with score labels (the money shot)
and prints attention + brand-fit (Critic) deltas.
"""
from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import agents
import deepgaze_runner as dg

_SAMPLES = Path(__file__).parents[1] / "frontend" / "public" / "samples"
_OUT = Path(__file__).with_name("demo_out")
_DEPTH = 2  # showcase depth (live path uses 1); deeper = stronger, slower

# Curated target boxes (normalized [x,y,w,h]) — mirror frontend/src/samples.ts so the
# baseline is meaningful (auto-detect gives a noisy box). These are the brand's intended
# focus (logo/product) we score attention against.
_TARGETS: dict[str, list[float]] = {
    "coca-cola": [0.33, 0.28, 0.33, 0.64],
    "nike": [0.30, 0.18, 0.45, 0.30],
    "apple": [0.32, 0.20, 0.36, 0.62],
    "mcdonalds": [0.26, 0.31, 0.52, 0.33],
    "red-bull": [0.44, 0.33, 0.21, 0.34],   # tight on the can (clutter redirect = real headroom)
    "spotify": [0.29, 0.36, 0.28, 0.40],     # tight on the phone in hand
    "pepsi": [0.33, 0.30, 0.34, 0.45],
    "liquid-death": [0.30, 0.22, 0.36, 0.64],
}


def _load(name: str) -> Image.Image:
    for ext in (".jpg", ".jpeg", ".png"):
        p = _SAMPLES / f"{name}{ext}"
        if p.exists():
            return Image.open(p).convert("RGB")
    raise FileNotFoundError(f"no sample image for {name!r} in {_SAMPLES}")


def _from_data_url(u: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(u.split(",", 1)[-1]))).convert("RGB")


def _font(size: int):
    for f in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _compare(before: Image.Image, after: Image.Image, res: dict, brand: str) -> Image.Image:
    """Side-by-side before|after with a header band carrying the score story."""
    h = 720
    def fit(im):
        w = int(im.width * h / im.height)
        return im.resize((w, h), Image.LANCZOS)
    b, a = fit(before), fit(after)
    pad, band = 24, 132
    W = b.width + a.width + pad * 3
    H = h + band + pad * 2
    canvas = Image.new("RGB", (W, H), (17, 17, 20))
    canvas.paste(b, (pad, band + pad))
    canvas.paste(a, (pad * 2 + b.width, band + pad))

    d = ImageDraw.Draw(canvas)
    f_big, f_mid, f_sm = _font(46), _font(30), _font(24)
    base_pct = round(res["baseline_score"] * 100)
    fin_pct = round(res["final_score"] * 100)
    dpts = fin_pct - base_pct
    jq = res.get("judge_score")

    d.text((pad, 22), f"{brand.title()} — attention on target", font=f_mid, fill=(235, 235, 240))
    d.text((pad, 66), f"{base_pct}%  →  {fin_pct}%", font=f_big, fill=(255, 255, 255))
    tw = d.textlength(f"{base_pct}%  →  {fin_pct}%", font=f_big)
    sign = "+" if dpts >= 0 else ""
    d.text((pad + tw + 26, 78), f"{sign}{dpts} pts", font=f_mid, fill=(80, 220, 120))
    jtxt = f"Judge brand-fit: {round(jq * 100)}%" if jq is not None else "Judge: kept original"
    d.text((W - 440, 40), jtxt, font=f_sm, fill=(200, 200, 210))
    d.text((W - 440, 84), "DeepGaze IIE objective + Gemini Judge", font=f_sm, fill=(140, 140, 150))

    lf = _font(26)
    d.text((pad + 8, band + pad + 8), "BEFORE", font=lf, fill=(255, 255, 255))
    d.text((pad * 2 + b.width + 8, band + pad + 8), "AFTER", font=lf, fill=(120, 240, 150))
    return canvas


def run_brand(brand: str) -> None:
    img = _load(brand)
    print(f"\n=== {brand} ({img.width}x{img.height}) ===")
    res = agents.run(img, brand=brand, target=_TARGETS.get(brand), depth=_DEPTH)

    real = "DeepGaze IIE" if dg._model is not None else "edge+center FALLBACK"
    jq = res.get("judge_score")
    print(f"  saliency engine : {real}")
    print(f"  attention       : {res['baseline_score']:.3f} -> {res['final_score']:.3f}"
          f"  (+{round((res['final_score'] - res['baseline_score']) * 100)} pts)")
    print(f"  Judge brand-fit : {jq if jq is not None else 'kept original'}")
    judge_step = next((s for s in res.get("iterations", []) if s["agent"] == "Judge"), None)
    if judge_step:
        print(f"  Judge verdict   : {judge_step['summary']}")

    out = _OUT / brand
    out.mkdir(parents=True, exist_ok=True)
    after = _from_data_url(res["variant_png"])
    img.save(out / "before.png")
    after.save(out / "after.png")
    _from_data_url(res["heatmap_before"]).save(out / "heatmap_before.png") if res["heatmap_before"].startswith("data") else None
    _from_data_url(res["heatmap_after"]).save(out / "heatmap_after.png") if res["heatmap_after"].startswith("data") else None
    _compare(img, after, res, brand).save(out / "compare.png")
    print(f"  saved           : {out / 'compare.png'}")


if __name__ == "__main__":
    brands = sys.argv[1:] or ["nike", "red-bull"]
    for b in brands:
        try:
            run_brand(b)
        except Exception as e:
            print(f"  !! {b} failed: {type(e).__name__}: {e}")
    print(f"\nAll outputs under: {_OUT}")
