"""Regenerate every figure in the README from data that lives in this repo.

    python scripts/make_figures.py

Reads the captured winning run in frontend/public/precomputed/nike.json, re-scores
the before and after with the CURRENT scorer, and writes assets/media/hero-before-after.png.
The shared drawing helpers here are also used by make_showcase.py. Every number printed on a figure is measured at build
time, so a figure can never drift away from the code that produced it.

Needs the backend deps (torch + DeepGaze). Pass --no-score to redraw the layout
without loading the model.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "media"
RUN = ROOT / "frontend" / "public" / "precomputed" / "nike.json"
SAMPLES = ROOT / "frontend" / "public" / "samples"

# App palette (frontend/src/index.css :root)
BG, INK, MUTED, LINE = "#faf7f1", "#1b1813", "#8a8478", "#ebe4d6"
ACCENT, ACCENT_INK, GOOD, GOOD_WASH, PANEL = "#ee3d23", "#c22d16", "#0e9f6e", "#e6f6ef", "#ffffff"

NIKE_BOX = [0.3, 0.18, 0.45, 0.3]  # frontend/src/samples.ts


def font(name: str, size: int):
    for candidate in (name, "arial.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def DISPLAY(s):
    return font("georgiab.ttf", s)


def SERIF(s):
    return font("georgia.ttf", s)


def MONO(s):
    return font("consola.ttf", s)


def MONOB(s):
    return font("consolab.ttf", s)


def SANSB(s):
    return font("calibrib.ttf", s)


def load_run() -> dict:
    return json.loads(RUN.read_text(encoding="utf-8"))


def data_url_image(url: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[-1]))).convert("RGB")


def rounded(img: Image.Image, r: int = 14) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1], r, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def fit(img: Image.Image, w: int, h: int) -> Image.Image:
    c = img.copy()
    c.thumbnail((w, h), Image.LANCZOS)
    return c


def chip(d: ImageDraw.ImageDraw, xy, text, fg, bg, f, pad=(11, 6)):
    x, y = xy
    tw = d.textlength(text, font=f)
    th = f.size + 2
    d.rounded_rectangle([x, y, x + tw + pad[0] * 2, y + th + pad[1] * 2], 999, fill=bg)
    d.text((x + pad[0], y + pad[1]), text, font=f, fill=fg)


def heat_rgba(density: np.ndarray, pct: float = 98.0, gamma: float = 0.65, amax: int = 205):
    """Percentile-normalized heat layer. Max-normalizing a DeepGaze density leaves ~94%
    of the frame under 10% opacity (measured), so normalize against a high percentile."""
    n = np.clip(density / (np.percentile(density, pct) + 1e-12), 0, 1)
    rgba = np.zeros((*n.shape, 4), np.uint8)
    rgba[..., 0] = 255
    rgba[..., 1] = (np.clip(1 - n, 0, 1) * 195).astype(np.uint8)
    rgba[..., 3] = (n ** gamma * amax).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def overlay_heat(img: Image.Image, density: np.ndarray) -> Image.Image:
    layer = heat_rgba(density).resize(img.size, Image.BILINEAR)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def fig_hero(scores: dict | None, dens: dict | None = None):
    """assets/media/hero-before-after.png - the captured winning run, re-scored today.
    With densities, each pane carries its DeepGaze heat layer so the move is visible."""
    run = load_run()
    before, after = data_url_image(run["original_png"]), data_url_image(run["variant_png"])
    PW, PH = 620, 930
    W, H = 1440, 1330 if scores else 1190
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)

    d.text((60, 52), "One campaign, one branch of the search", font=DISPLAY(38), fill=INK)
    d.text((60, 106), "Nike billboard with DeepGaze attention on top. Before, the strongest pull is the "
                      "Subway sign. After the edit, it moves up onto the player.", font=SERIF(21), fill=MUTED)

    y0 = 172
    for i, (label, img) in enumerate((("BEFORE", before), ("AFTER", after))):
        k = "before" if i == 0 else "after"
        if dens:
            img = overlay_heat(img, dens[k])
        x0 = 60 + i * (PW + 60)
        pane = fit(img, PW, PH)
        px = x0 + (PW - pane.size[0]) // 2
        d.rounded_rectangle([x0 - 10, y0 - 10, x0 + PW + 10, y0 + PH + 10], 18, fill=PANEL, outline=LINE)
        canvas.paste(rounded(pane, 12), (px, y0), rounded(pane, 12))
        chip(d, (x0, y0 + PH + 24), label, "#ffffff", INK if i == 0 else GOOD, MONOB(16))
        if scores:
            d.text((x0 + 112, y0 + PH + 28),
                   "prominence {:.0f}   on-target salience {:.0f}".format(
                       scores[k]["prom"] * 100, scores[k]["abs"] * 100),
                   font=MONO(18), fill=MUTED)

    if scores:
        dp = (scores["after"]["prom"] - scores["before"]["prom"]) * 100
        da = (scores["after"]["abs"] - scores["before"]["abs"]) * 100
        bx, by = 60, y0 + PH + 76
        d.rounded_rectangle([bx, by, W - 60, by + 112], 16, fill=GOOD_WASH, outline="#bfe7d6")
        for dx, val, lbl in ((26, dp, "pts size-invariant prominence"),
                             (560, da, "pts absolute on-target salience")):
            txt = "{:+.1f}".format(val)
            d.text((bx + dx, by + 18), txt, font=DISPLAY(46), fill=GOOD)
            d.text((bx + dx + d.textlength(txt, font=DISPLAY(46)) + 12, by + 40), lbl,
                   font=SANSB(20), fill=GOOD)
        d.text((bx + 26, by + 76),
               "re-measured by scripts/make_figures.py against the current scorer"
               "   ·   reward-hack guard: {}".format(scores["guard"]), font=MONO(15), fill="#5f8f79")
    canvas.save(OUT / "hero-before-after.png")
    print("hero-before-after.png", canvas.size)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-score", action="store_true", help="skip figures that need the model")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.no_score:
        fig_hero(None)
        return
    sys.path.insert(0, str(ROOT / "backend"))
    import deepgaze_runner as dg
    import eval_guard
    run = load_run()
    scores, dens = {}, {}
    for k, key in (("before", "original_png"), ("after", "variant_png")):
        img = data_url_image(run[key])
        prom, abs_ = dg.score_components(img, NIKE_BOX)
        scores[k] = {"prom": prom, "abs": abs_}
        dens[k] = dg._density(np.asarray(img))
        print("  re-scored {}: prominence={} on-target salience={}".format(k, prom, abs_))
    g = eval_guard.verdict(data_url_image(run["original_png"]), data_url_image(run["variant_png"]),
                           ratio_before=scores["before"]["prom"], ratio_after=scores["after"]["prom"],
                           target_sal_before=scores["before"]["abs"], target_sal_after=scores["after"]["abs"])
    scores["guard"] = g["decision"]
    print("  guard:", g["decision"], g["reasons"])
    fig_hero(scores, dens)


if __name__ == "__main__":
    main()
