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
async def run_agents(image: UploadFile = File(...), brand: str = Form("the brand")) -> dict:
    return agents.run(await _image(image), brand)


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
