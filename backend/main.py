"""Pixel backend — FastAPI app. Endpoints match the frozen contract (WORK_ALLOCATION.md).

Run:  uvicorn main:app --reload --port 8000   (from backend/)
"""
from __future__ import annotations

import base64
import io
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

import agents
import deepgaze_runner as dg
import gemini
import storage

@asynccontextmanager
async def _lifespan(_app):
    try:  # warm DeepGaze at boot so the first real /predict isn't an 8s stall
        import numpy as np
        dg.predict(Image.fromarray(np.zeros((64, 64, 3), np.uint8)))
    except Exception:
        pass
    yield


app = FastAPI(title="Pixel backend", lifespan=_lifespan)

# Frontend dev server (Vite). Open in dev; tighten for any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _image(file: UploadFile) -> Image.Image:
    return Image.open(io.BytesIO(await file.read())).convert("RGB")


def _data_url_to_image(data_url: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[-1]))).convert("RGB")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "gemini": gemini.settings.has_gemini, "pinecone": gemini.settings.has_pinecone}


@app.post("/predict")
async def predict(image: UploadFile = File(...), target: str | None = Form(None)) -> dict:
    img = await _image(image)
    box = json.loads(target) if target else None
    result = dg.predict(img, box)
    gemini.label_distractors(img, result["distractors"])  # name what each thief actually is
    return result


@app.post("/edit")
async def edit(image: UploadFile = File(...), directive: str = Form(...)) -> dict:
    variant, desc = gemini.edit_image(await _image(image), directive)
    return {
        "variant_png": dg.to_data_url(variant),
        "edit_description": desc,
        "width": variant.size[0],
        "height": variant.size[1],
    }


@app.post("/agents")
async def run_agents(image: UploadFile = File(...), brand: str = Form("the brand"),
                     target: str | None = Form(None)) -> dict:
    box = json.loads(target) if target else None
    return agents.run(await _image(image), brand, box)


def _stepwise_order(pool: list[str]) -> list[str]:
    """Rank directives so the first branches are the most reliable attention-raisers.
    0 = amplify the brand (enlarge/brighten/add CTA), 1 = neutral, 2 = risky/structural."""
    def rank(d: str) -> int:
        head = d.lower().lstrip()  # rank by the leading verb, not mid-sentence words
        if head.startswith(("add", "enlarge", "clearly enlarge", "boost", "make", "brighten")):
            return 0  # amplify the brand — most reliable lift
        if head.startswith(("remove", "reframe", "recolor", "clearly tone", "tone")):
            return 2  # structural / risky — can regress, try later
        return 1
    return sorted(pool, key=rank)


@app.post("/optimize/step")
async def optimize_step(image: UploadFile = File(...), brand: str = Form("the brand"),
                        target: str | None = Form(None), step: int = Form(0),
                        hint: str = Form("")) -> dict:
    """One branch at a time. `image` is the CURRENT best creative (the original on step 0);
    the frontend re-sends the adopted winner each step. We run a single Nano Banana edit
    (next directive in the pool), re-score with DeepGaze, and Judge it. The frontend shows
    this one branch and asks the user whether to spawn another."""
    img = await _image(image)
    box = json.loads(target) if target else None
    before = dg.predict(img, box)
    tbox = box or before["target_box"]
    current = before["attention_score"]

    # One branch at a time, so ORDER matters (the parallel search hid bad directives by
    # keeping the best of N). Lead with "amplify the brand" edits — reliably raise attention —
    # before the riskier structural ones (remove/reframe/recolor) that can regress.
    pool = _stepwise_order(agents._directive_pool(before, {}, brand))
    directive = pool[step % len(pool)]
    if hint.strip():  # the user's own suggestion, applied on top of the auto edit
        directive = f"{directive}. Also apply the user's request: {hint.strip()}"
    variant, desc = gemini.edit_image(img, directive)
    new_score = dg.score_only(variant, tbox)
    quality, reason = gemini.judge(variant, brand)
    vetoed = quality < gemini.settings.judge_gate
    return {
        "step": step,
        "directive": desc,
        "variant_png": dg.to_data_url(variant),
        "current_score": round(current, 4),
        "new_score": round(new_score, 4),
        "delta": round(new_score - current, 4),
        "judge": round(quality, 3),
        "judge_reason": reason,
        "vetoed": vetoed,
        "improved": bool(new_score > current and not vetoed),
        "n_directives": len(pool),
    }


# --- Campaigns: save / list / resume / optimize ---------------------------------
@app.post("/campaigns")
async def create_campaign(image: UploadFile = File(...), name: str = Form(""),
                          brand: str = Form("the brand")) -> dict:
    rec = storage.create_campaign(name, brand, dg.to_data_url(await _image(image)))
    return {k: rec[k] for k in ("id", "name", "brand", "created_at")}


@app.get("/campaigns")
def list_campaigns() -> list[dict]:
    return storage.list_campaigns()


@app.get("/campaigns/{cid}")
def get_campaign(cid: str) -> dict:
    try:
        return storage.get_campaign(cid)
    except FileNotFoundError:
        raise HTTPException(404, "campaign not found")


@app.post("/campaigns/{cid}/optimize")
def optimize_campaign(cid: str, brand: str | None = Form(None)) -> dict:
    try:
        rec = storage.get_campaign(cid)
    except FileNotFoundError:
        raise HTTPException(404, "campaign not found")
    result = agents.run(_data_url_to_image(rec["original_png"]), brand or rec["brand"])
    return storage.save_run(cid, result)
