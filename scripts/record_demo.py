"""Record real backend responses for the static web demo.

    python scripts/record_demo.py                 # every sample that isn't recorded yet
    python scripts/record_demo.py nike apple      # just these (re-records them)

Calls the real FastAPI app in-process, the same way the frontend does: /predict on the
sample, then /optimize/step a few times, re-sending the current best creative after each
branch exactly like App.tsx. Needs GEMINI_API_KEY and DeepGaze. Writes
frontend/public/replay/<sample>/ with the JSON responses, the heatmaps and every edit,
which the demo build (npm run build:demo) replays with no backend.
"""
from __future__ import annotations

import base64
import io
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.testclient import TestClient  # noqa: E402

import deepgaze_runner as dg  # noqa: E402
import main  # noqa: E402

SAMPLES_TS = ROOT / "frontend" / "src" / "samples.ts"
PUBLIC = ROOT / "frontend" / "public"
OUT = PUBLIC / "replay"
STEPS = 4
EDIT_MAX = 1400  # longest side of the saved edit images; scoring happens at full size


def samples() -> list[dict]:
    src = SAMPLES_TS.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r'id: "([^"]+)",\s*brand: "([^"]+)".*?target_box: \[([^\]]+)\]', src, re.S):
        out.append({"id": m.group(1), "brand": m.group(2),
                    "box": [float(v) for v in m.group(3).split(",")]})
    return out


def decode(data_url: str) -> bytes:
    return base64.b64decode(data_url.split(",", 1)[-1])


def save_jpg(raw: bytes, path: Path, max_side: int) -> None:
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    img.save(path, quality=84, optimize=True, progressive=True)


def record(client: TestClient, s: dict) -> None:
    sid, box = s["id"], json.dumps(s["box"])
    out = OUT / sid
    out.mkdir(parents=True, exist_ok=True)
    src = (PUBLIC / "samples" / (sid + ".jpg")).read_bytes()
    save_jpg(src, out / "thumb.jpg", 560)

    r = client.post("/predict", files={"image": (sid + ".jpg", src, "image/jpeg")},
                    data={"target": box})
    r.raise_for_status()
    pred = r.json()
    if pred.get("engine") != "deepgaze-iie":
        sys.exit("DeepGaze did not load (engine={}); refusing to record fallback scores".format(pred.get("engine")))
    (out / "heat.png").write_bytes(decode(pred["heatmap_png"]))
    pred["heatmap_png"] = "replay/{}/heat.png".format(sid)
    pred.pop("target_salience", None)
    pred.pop("engine", None)
    (out / "predict.json").write_text(json.dumps(pred, indent=1), encoding="utf-8")
    print("{:14s} predict  {:.0f}  thief: {}".format(sid, pred["attention_score"] * 100,
                                                    pred["distractors"][0]["desc"] if pred["distractors"] else "-"))

    best, best_score, steps = src, pred["attention_score"], []
    for k in range(STEPS):
        t = time.time()
        r = client.post("/optimize/step", files={"image": ("best.png", best, "image/png")},
                        data={"brand": s["brand"], "target": box, "step": str(k)})
        r.raise_for_status()
        res = r.json()
        if res["directive"].startswith("["):
            sys.exit("step {} on {} did not produce a real edit: {}".format(k, sid, res["directive"][:80]))
        raw = decode(res["variant_png"])
        save_jpg(raw, out / "step{}.jpg".format(k), EDIT_MAX)
        heat = dg.predict(Image.open(io.BytesIO(raw)).convert("RGB"), s["box"])["heatmap_png"]
        (out / "step{}-heat.png".format(k)).write_bytes(decode(heat))
        res["variant_png"] = "replay/{}/step{}.jpg".format(sid, k)
        res["variant_heatmap"] = "replay/{}/step{}-heat.png".format(sid, k)
        steps.append(res)
        # Same rule as App.tsx runBranch: only a winning branch becomes the next base.
        if res["improved"] and res["new_score"] > best_score:
            best, best_score = raw, res["new_score"]
        print("{:14s} step {}   {:.0f} -> {:.0f}  judge {:.2f}  guard {:6s} improved={}  ({:.0f}s)".format(
            sid, k, res["current_score"] * 100, res["new_score"] * 100, res["judge"],
            res["guard"], res["improved"], time.time() - t))
    (out / "steps.json").write_text(json.dumps(steps, indent=1), encoding="utf-8")


def main_() -> None:
    want = sys.argv[1:]
    client = TestClient(main.app)
    with client:
        for s in samples():
            if want and s["id"] not in want:
                continue
            if not want and (OUT / s["id"] / "steps.json").exists():
                continue
            record(client, s)
    rec = sorted(p.name for p in OUT.iterdir() if (p / "steps.json").exists())
    (OUT / "manifest.json").write_text(json.dumps(
        {"recorded": date.today().isoformat(), "engine": "deepgaze-iie", "device": dg.device_name(),
         "samples": rec}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main_()
