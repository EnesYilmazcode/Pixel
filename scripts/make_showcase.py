"""DeepGaze showcase figures for the README: a gallery of every sample ad and an
animated hero GIF.

    python scripts/make_showcase.py

Runs DeepGaze IIE on the sample ads in frontend/public/samples/ with the target boxes
from frontend/src/samples.ts, and writes assets/media/gallery.png and
assets/media/deepgaze.gif. Every score is measured when the script runs.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_figures import (ACCENT, BG, DISPLAY, GOOD, INK, LINE, MONO, MONOB, MUTED,  # noqa: E402
                          OUT, PANEL, ROOT, SAMPLES, SERIF, heat_rgba, rounded)

sys.path.insert(0, str(ROOT / "backend"))
import deepgaze_runner as dg  # noqa: E402

GIF_ORDER = ["nike", "the-ordinary", "red-bull", "coca-cola"]


def load_samples() -> list[dict]:
    src = (ROOT / "frontend" / "src" / "samples.ts").read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r'id: "([^"]+)",\s*brand: "([^"]+)".*?target_box: \[([^\]]+)\]', src, re.S):
        out.append({"id": m.group(1), "brand": m.group(2),
                    "box": [float(v) for v in m.group(3).split(",")]})
    return out


def analyze(s: dict) -> dict:
    img = Image.open(SAMPLES / (s["id"] + ".jpg")).convert("RGB")
    rep = dg.predict(img, s["box"])
    rep["density"] = dg._density(np.asarray(img))
    rep["img"] = img
    return rep


def draw_path(im: Image.Image, scan: list[dict], upto: float, box=None) -> Image.Image:
    """Numbered fixations. `upto` is how many fixations to show; a fractional part
    draws the line toward the next one partway."""
    im = im.convert("RGB").copy()
    d = ImageDraw.Draw(im, "RGBA")
    W, H = im.size
    s = max(2, W // 200)
    if box:
        x0, y0 = box[0] * W, box[1] * H
        x1, y1 = (box[0] + box[2]) * W, (box[1] + box[3]) * H
        for i in range(int(x0), int(x1), 18):
            d.line([(i, y0), (min(i + 9, x1), y0)], fill=GOOD, width=s)
            d.line([(i, y1), (min(i + 9, x1), y1)], fill=GOOD, width=s)
        for j in range(int(y0), int(y1), 18):
            d.line([(x0, j), (x0, min(j + 9, y1))], fill=GOOD, width=s)
            d.line([(x1, j), (x1, min(j + 9, y1))], fill=GOOD, width=s)
    pts = [(p["x"] * W, p["y"] * H) for p in sorted(scan, key=lambda p: p["order"])]
    n = int(upto)
    seg = pts[:n]
    if n < len(pts) and upto > n and n >= 1:
        (ax, ay), (bx, by) = pts[n - 1], pts[n]
        t = upto - n
        seg = seg + [(ax + (bx - ax) * t, ay + (by - ay) * t)]
    if len(seg) > 1:
        d.line(seg, fill=(255, 255, 255, 235), width=s + 2, joint="curve")
    r = max(12, W // 26)
    for i, (x, y) in enumerate(pts[:n]):
        x, y = min(max(x, r + 2), W - r - 2), min(max(y, r + 2), H - r - 2)
        d.ellipse([x - r, y - r, x + r, y + r], fill=ACCENT, outline="#ffffff", width=max(2, s))
        nf = MONOB(int(r * 1.15))
        d.text((x - d.textlength(str(i + 1), font=nf) / 2, y - nf.size * 0.62), str(i + 1),
               font=nf, fill="#ffffff")
    return im


def with_heat(img: Image.Image, density: np.ndarray, alpha: float = 1.0) -> Image.Image:
    layer = heat_rgba(density).resize(img.size, Image.BILINEAR)
    if alpha < 1.0:
        a = np.asarray(layer).copy()
        a[..., 3] = (a[..., 3] * alpha).astype(np.uint8)
        layer = Image.fromarray(a, "RGBA")
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def framed(rep: dict, w: int, h: int, box=None):
    """Center-crop the ad to exactly w x h, and move the density, fixations and box
    into the cropped frame so nothing is drawn against a region that got cut off."""
    sw, sh = rep["img"].size
    scale = max(w / sw, h / sh)
    rw, rh = round(sw * scale), round(sh * scale)
    L, T = (rw - w) // 2, (rh - h) // 2
    img = rep["img"].resize((rw, rh), Image.LANCZOS).crop((L, T, L + w, T + h))
    dens = np.asarray(Image.fromarray(rep["density"].astype(np.float32)).resize((rw, rh), Image.BILINEAR))
    dens = dens[T:T + h, L:L + w]
    scan = [{"x": (p["x"] * rw - L) / w, "y": (p["y"] * rh - T) / h, "order": p["order"]}
            for p in rep["scanpath"]]
    nbox = None
    if box:
        nbox = [(box[0] * rw - L) / w, (box[1] * rh - T) / h, box[2] * rw / w, box[3] * rh / h]
    return img, dens, scan, nbox


def fig_gallery(reps: list[tuple[dict, dict]]):
    TW, TH, GAP, M, SS = 330, 495, 26, 50, 2
    cols = 4
    rows = (len(reps) + cols - 1) // cols
    W = M * 2 + cols * TW + (cols - 1) * GAP
    H = 150 + rows * (TH + 84) + 30
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    d.text((M, 42), "Where DeepGaze says people will look", font=DISPLAY(36), fill=INK)
    d.text((M, 94), "Every sample ad in the app, one pass each. Red is predicted attention, "
                    "the numbers are the first five fixations, the dashed box is the brand.",
           font=SERIF(19), fill=MUTED)
    for k, (s, rep) in enumerate(reps):
        c, r = k % cols, k // cols
        x0, y0 = M + c * (TW + GAP), 150 + r * (TH + 84)
        img, dens, scan, box = framed(rep, TW * SS, TH * SS, s["box"])
        tile = draw_path(with_heat(img, dens), scan, 5, box).resize((TW, TH), Image.LANCZOS)
        tile = rounded(tile, 12)
        d.rounded_rectangle([x0 - 6, y0 - 6, x0 + TW + 6, y0 + TH + 6], 14, fill=PANEL, outline=LINE)
        canvas.paste(tile, (x0, y0), tile)
        score = rep["attention_score"] * 100
        d.text((x0, y0 + TH + 16), s["brand"], font=MONOB(18), fill=INK)
        d.text((x0, y0 + TH + 44), "attention on target {:.0f}".format(score), font=MONO(16),
               fill=GOOD if score >= 50 else ACCENT)
    canvas.save(OUT / "gallery.png", optimize=True)
    print("gallery.png", canvas.size)


def fig_gif(reps: dict[str, tuple[dict, dict]]):
    W, H = 400, 600
    frames, durs = [], []

    def add(im, ms):
        frames.append(im)
        durs.append(ms)

    order = [reps[k] for k in GIF_ORDER if k in reps]
    shots = []
    for s, rep in order:
        img, dens, scan, _ = framed(rep, W, H)
        shots.append((img, dens, scan))
    finals = [draw_path(with_heat(i, dn), sc, 5) for i, dn, sc in shots]

    for idx, (img, dens, scan) in enumerate(shots):
        full = with_heat(img, dens)
        if idx == 0:
            add(finals[0], 1500)  # open on the finished result
            for t in (0.33, 0.66, 1.0):
                add(Image.blend(finals[0], img, t), 70)
        add(img, 600)
        for a in (0.2, 0.4, 0.6, 0.8, 1.0):
            add(with_heat(img, dens, a), 80)
        for u in np.arange(1.5, 5.01, 0.5):
            add(draw_path(full, scan, float(u)), 70 if u % 1 else 220)
        add(finals[idx], 1700)
        nxt = shots[idx + 1][0] if idx < len(shots) - 1 else finals[0]
        for t in (0.33, 0.66, 1.0):
            add(Image.blend(finals[idx], nxt, t), 70)
    # One shared palette keeps the file small and stops colors shimmering between frames.
    sheet = Image.new("RGB", (W, H * len(finals)))
    for i, f in enumerate(finals):
        sheet.paste(f, (0, H * i))
    pal = sheet.quantize(colors=200, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    q[0].save(OUT / "deepgaze.gif", save_all=True, append_images=q[1:], duration=durs, loop=0,
              optimize=True)
    print("deepgaze.gif", len(frames), "frames", (OUT / "deepgaze.gif").stat().st_size // 1024, "KB")


# First match wins, so the combined directive (which also mentions a headline) goes first.
SHORT = [("SEVERAL", "several at once"), ("headline", "headline + CTA"),
         ("enlarge", "enlarge product"), ("reframe", "head-on reframe"), ("remove", "remove clutter")]


def fig_every_edit(sample: str = "the-ordinary"):
    """assets/media/every-edit.png - every Nano Banana edit from one captured run,
    each re-scored by DeepGaze against the same fixed brand box."""
    run_dir = ROOT / "results" / sample
    if not (run_dir / "run.json").exists():
        print("every-edit.png skipped: run scripts/capture_run.py first")
        return
    import json
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    box = run["box"]
    base = run["base"]["prom"]
    tiles = [("original", Image.open(SAMPLES / (sample + ".jpg")).convert("RGB"), base)]
    for e in run["edits"]:
        label = next((v for k, v in SHORT if k in e["directive"]), e["directive"][:24])
        tiles.append((label, Image.open(run_dir / "edit{}.jpg".format(e["k"])).convert("RGB"), e["prom"]))

    TW, TH, GAP, M, SS = 220, 330, 18, 50, 2
    W = M * 2 + len(tiles) * TW + (len(tiles) - 1) * GAP
    H = 150 + TH + 110
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    d.text((M, 42), "Five real edits, all scored lower", font=DISPLAY(36), fill=INK)
    d.text((M, 94), "The Ordinary sample, one live run. Each edit is scored against the same "
                    "brand box. None beat the original, so Pixel kept it.", font=SERIF(19), fill=MUTED)
    for i, (label, img, prom) in enumerate(tiles):
        x0, y0 = M + i * (TW + GAP), 150
        rep = {"img": img, "density": dg._density(np.asarray(img)), "scanpath": []}
        im, dens, _, nbox = framed(rep, TW * SS, TH * SS, box)
        tile = rounded(draw_path(with_heat(im, dens, 0.85), [], 0, nbox).resize((TW, TH), Image.LANCZOS), 10)
        edge = INK if i == 0 else LINE
        d.rounded_rectangle([x0 - 5, y0 - 5, x0 + TW + 5, y0 + TH + 5], 12, fill=PANEL, outline=edge,
                            width=2 if i == 0 else 1)
        canvas.paste(tile, (x0, y0), tile)
        d.text((x0, y0 + TH + 16), label, font=MONOB(15), fill=INK)
        if i == 0:
            d.text((x0, y0 + TH + 42), "{:.0f}  kept".format(prom * 100), font=MONO(16), fill=GOOD)
        else:
            d.text((x0, y0 + TH + 42), "{:.0f}  ({:+.0f})".format(prom * 100, (prom - base) * 100),
                   font=MONO(16), fill=ACCENT)
    canvas.save(OUT / "every-edit.png", optimize=True)
    print("every-edit.png", canvas.size)


def main():
    samples = load_samples()
    reps = []
    for s in samples:
        rep = analyze(s)
        print("  {:<14} on target {:.2f}  engine {} on {}".format(
            s["id"], rep["attention_score"], dg.engine_name(), dg.device_name()))
        reps.append((s, rep))
    if dg.engine_name() != "deepgaze-iie":
        sys.exit("DeepGaze did not load; refusing to draw figures from the fallback engine")
    fig_gallery(reps)
    fig_gif({s["id"]: (s, r) for s, r in reps})
    fig_every_edit()


if __name__ == "__main__":
    main()
