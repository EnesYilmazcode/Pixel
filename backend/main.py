"""Pixel backend — FastAPI app. Endpoints match the frozen contract (WORK_ALLOCATION.md).

Run:  uvicorn main:app --reload --port 8000   (from backend/)
"""
from __future__ import annotations

import io
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

import agents
import deepgaze_runner as dg
import gemini

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


@app.get("/health")
def health() -> dict:
    return {"ok": True, "gemini": gemini.settings.has_gemini, "pinecone": gemini.settings.has_pinecone}


@app.post("/predict")
async def predict(image: UploadFile = File(...), target: str | None = Form(None)) -> dict:
    box = json.loads(target) if target else None
    return dg.predict(await _image(image), box)


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
