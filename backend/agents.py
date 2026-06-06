"""The Director loop — single-variant MVP (baseline → directive → edit → re-score).

Insider/Scout are stubbed here and become real in Phase 2 (Gemini brief + Pinecone
RAG). Branching/Judge (branch.py) layers on top once this 1-variant loop is green.
Returns an AgentsResult-shaped dict (see schemas.py / the frozen contract).
"""
from __future__ import annotations

from PIL import Image

import competitive
import deepgaze_runner as dg
import gemini
from config import settings


def insider(brand: str) -> dict:
    """Insider agent — our-brand brief (real Gemini call, neutral fallback)."""
    return gemini.brand_brief(brand)


def scout(brand: str, brief: dict) -> dict:
    """Scout agent — competitor tactics via Pinecone RAG (see competitive.py)."""
    return competitive.scout(brand, brief)


def _propose_directives(before: dict, insights: dict, n: int) -> list[str]:
    """N diverse edit hypotheses — each branch tests a different idea."""
    out = []
    if before["distractors"]:
        out.append(f"reduce the visual weight of the {before['distractors'][0]['desc']} "
                   "so it stops drawing the eye")
    out += [t["apply"] for t in insights.get("tactics", [])]
    out.append("increase the contrast and saturation of the main product so it is the clear focal point")
    seen, uniq = set(), []
    for d in out:
        if d and d not in seen:
            seen.add(d)
            uniq.append(d)
    return uniq[: max(1, n)]


def run(image: Image.Image, brand: str = "the brand") -> dict:
    """Single-round best-of-N: try N edits, keep the best that beats baseline.
    Never regresses (the original is the floor) — the score only ever goes up."""
    target = gemini.detect_target(image)
    before = dg.predict(image, target)
    baseline = before["attention_score"]
    brief = insider(brand)
    insights = scout(brand, brief)

    # Retoucher proposes + applies N edits; Eye scores each; keep the best.
    best = {"score": baseline, "img": image, "desc": "kept original (no edit beat baseline)"}
    for directive in _propose_directives(before, insights, settings.breadth):
        variant, desc = gemini.edit_image(image, directive)
        score = dg.score_only(variant, target)
        if score > best["score"]:
            best = {"score": score, "img": variant, "desc": desc}

    improved = best["img"] is not image
    after = dg.predict(best["img"], target) if improved else before
    final = after["attention_score"]
    thief = before["distractors"][0]["desc"] if before["distractors"] else "competing elements"

    steps = [
        {"agent": "Insider", "status": "done", "summary": f"{brand}: {brief.get('tone', '')}"[:90]},
        {"agent": "Scout", "status": "done",
         "summary": insights["tactics"][0]["tactic"] if insights.get("tactics") else "no tactics"},
        {"agent": "Eye", "status": "done", "summary": f"baseline {round(baseline * 100)}% on target"},
        {"agent": "Retoucher", "status": "done",
         "summary": f"tried {settings.breadth} edits; best: {best['desc']}"[:110]},
        {"agent": "Eye", "status": "done", "summary": f"best {round(final * 100)}% on target"},
    ]

    return {
        "baseline_score": baseline,
        "final_score": final,
        "delta": round(final - baseline, 4),
        "brand_brief": brief,
        "competitive_insights": insights,
        "heatmap_before": before["heatmap_png"],
        "heatmap_after": after["heatmap_png"],
        "variant_png": dg.to_data_url(best["img"]),
        "rationale": (f"Reduced the {thief} and amplified the brand target; "
                      f"kept the best of {settings.breadth} agent edits."),
        "iterations": steps,
    }
