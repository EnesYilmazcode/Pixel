"""Gemini wrappers: localized image edit, target detection, LLM-as-judge.

Every function degrades gracefully when GEMINI_API_KEY is absent so the agent
loop still runs end-to-end in mock mode (returns the input unchanged / neutral
scores). Real calls use the pinned models in config.py.
"""
from __future__ import annotations

import io
import json

from PIL import Image

from config import settings
from deepgaze_runner import align_to_input

_client = None


def _genai():
    """Lazy google-genai client; None if no key, or if the SDK isn't installed yet
    (so the loop stays runnable in mock mode even with a key present)."""
    global _client
    if _client is not None or not settings.has_gemini:
        return _client
    try:
        from google import genai
        _client = genai.Client(api_key=settings.gemini_api_key)
    except Exception:
        _client = None
    return _client


# Google's documented localized-edit template (keeps composition/dims stable).
_EDIT_TMPL = (
    "Using the provided image, {directive}. Keep everything else exactly the same — "
    "preserve composition, framing, lighting, and the position and size of the logo and "
    "product. Do not change the aspect ratio or crop the image."
)


def edit_image(image: Image.Image, directive: str) -> tuple[Image.Image, str]:
    """Apply ONE localized edit. Returns (aligned_variant, description).
    No key -> returns the input unchanged (loop still demonstrable on mock scores)."""
    client = _genai()
    in_w, in_h = image.size
    if client is None:
        return image, f"[mock] would: {directive}"

    resp = client.models.generate_content(
        model=settings.gemini_image_model,
        contents=[_EDIT_TMPL.format(directive=directive), image],
    )
    for part in resp.candidates[0].content.parts:
        if getattr(part, "inline_data", None):
            variant = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
            return align_to_input(variant, in_w, in_h), directive
    return image, f"[no image returned] {directive}"


def detect_target(image: Image.Image, what: str = "primary logo or CTA") -> list[float]:
    """Return a normalized [x,y,w,h] box for the brand target. Falls back to center."""
    client = _genai()
    if client is None:
        return [0.35, 0.35, 0.30, 0.30]
    prompt = (
        f"Find the {what} in this ad. Respond with ONLY JSON "
        '{"x":..,"y":..,"w":..,"h":..} as fractions (0-1) of width/height.'
    )
    try:
        resp = client.models.generate_content(
            model=settings.gemini_text_model, contents=[prompt, image]
        )
        b = json.loads(_first_json(resp.text))
        return [float(b["x"]), float(b["y"]), float(b["w"]), float(b["h"])]
    except Exception:
        return [0.35, 0.35, 0.30, 0.30]


def judge(image: Image.Image, brand: str) -> tuple[float, str]:
    """LLM-as-judge: would this run as a real, on-brand ad? Returns (0..1, reason).
    Guards against attention-hacking (a garish logo that wins gaze but looks awful)."""
    client = _genai()
    if client is None:
        return 0.7, "[mock] looks plausible"
    prompt = (
        f"Rate this {brand} ad creative for quality and brand-fit (would it run as a real "
        'ad?). Respond ONLY JSON {"score":0..1,"reason":"..."}.'
    )
    try:
        resp = client.models.generate_content(
            model=settings.gemini_text_model, contents=[prompt, image]
        )
        j = json.loads(_first_json(resp.text))
        return float(j["score"]), str(j.get("reason", ""))
    except Exception:
        return 0.6, "[judge unavailable]"


_FALLBACK_BRIEF = {
    "audience": "broad consumer",
    "tone": "bold, confident",
    "palette": [],
    "dos": ["keep the product and logo dominant"],
    "donts": ["don't bury the call-to-action"],
}


def brand_brief(brand: str) -> dict:
    """Insider: a compact brand brief. Neutral fallback with no key."""
    client = _genai()
    if client is None:
        return dict(_FALLBACK_BRIEF)
    prompt = (
        f'Compact creative brief for the brand "{brand}". Respond ONLY JSON '
        '{"audience":..,"tone":..,"palette":[hex,...],"dos":[..],"donts":[..]}.'
    )
    try:
        resp = client.models.generate_content(model=settings.gemini_text_model, contents=prompt)
        b = json.loads(_first_json(resp.text))
        return {**_FALLBACK_BRIEF, **b}
    except Exception:
        return dict(_FALLBACK_BRIEF)


def name_regions(image: Image.Image, regions: list[list[float]]) -> list[str]:
    """Label what's actually inside each normalized [x,y,w,h] box (e.g. 'woman's face',
    'Coca-Cola can') so distractor callouts read like a human, not 'upper-left region'.
    Returns [] on no key/error — callers keep their own position labels."""
    client = _genai()
    if client is None or not regions:
        return []
    boxes = "; ".join(f"{i}:[{','.join(f'{v:.2f}' for v in r)}]" for i, r in enumerate(regions))
    prompt = (
        "Each box below is [x,y,w,h] as fractions of this image's width/height. "
        f"Name the main object inside each in 2-4 words. Boxes: {boxes}. "
        'Respond ONLY JSON {"labels":["..","..."]} in the same order.'
    )
    try:
        resp = client.models.generate_content(model=settings.gemini_text_model, contents=[prompt, image])
        labels = json.loads(_first_json(resp.text)).get("labels", [])
        return [str(x) for x in labels][: len(regions)]
    except Exception:
        return []


def label_distractors(image: Image.Image, distractors: list[dict]) -> None:
    """Replace each distractor's position label ('upper-left region') with the named
    object Gemini sees there ('woman's face'). Mutates in place; no-op without a key."""
    names = name_regions(image, [d["region"] for d in distractors])
    for d, nm in zip(distractors, names):
        if nm:
            d["desc"] = nm


def _first_json(text: str) -> str:
    s, e = text.find("{"), text.rfind("}")
    return text[s:e + 1] if s != -1 and e != -1 else "{}"
