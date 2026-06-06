"""The Director loop — single-variant MVP (baseline → directive → edit → re-score).

Insider/Scout are stubbed here and become real in Phase 2 (Gemini brief + Pinecone
RAG). Branching/Judge (branch.py) layers on top once this 1-variant loop is green.
Returns an AgentsResult-shaped dict (see schemas.py / the frozen contract).
"""
from __future__ import annotations

from PIL import Image

import deepgaze_runner as dg
import gemini


def insider(brand: str) -> dict:
    """Our-brand brief. TODO(Phase 2): one Gemini call from brand + uploaded assets."""
    return {
        "audience": "broad consumer",
        "tone": "bold, confident",
        "palette": [],
        "dos": ["keep the product and logo dominant"],
        "donts": ["don't bury the call-to-action"],
    }


def scout(brand: str, brief: dict) -> dict:
    """Competitor tactics. TODO(Phase 2): Pinecone RAG → Gemini synthesis."""
    return {
        "tactics": [
            {
                "tactic": "high-contrast CTA",
                "evidence": "category leaders",
                "apply": "boost the product/CTA contrast and saturation",
            }
        ]
    }


def _directive(baseline: dict, insights: dict) -> str:
    parts = []
    if baseline["distractors"]:
        parts.append(f"reduce the visual weight of the {baseline['distractors'][0]['desc']}")
    if insights.get("tactics"):
        parts.append(insights["tactics"][0]["apply"])
    return "; ".join(parts) or "make the product the clear focal point"


def run(image: Image.Image, brand: str = "the brand") -> dict:
    target = gemini.detect_target(image)
    before = dg.predict(image, target)
    brief = insider(brand)
    insights = scout(brand, brief)

    steps = [
        {"agent": "Insider", "status": "done", "summary": f"{brand}: {brief['tone']}"},
        {"agent": "Scout", "status": "done",
         "summary": insights["tactics"][0]["tactic"] if insights["tactics"] else "no tactics"},
        {"agent": "Eye", "status": "done",
         "summary": f"baseline {round(before['attention_score'] * 100)}% on target"},
    ]

    directive = _directive(before, insights)
    variant, desc = gemini.edit_image(image, directive)
    after = dg.predict(variant, target)

    steps += [
        {"agent": "Retoucher", "status": "done", "summary": desc},
        {"agent": "Eye", "status": "done",
         "summary": f"re-score {round(after['attention_score'] * 100)}% on target"},
    ]

    baseline, final = before["attention_score"], after["attention_score"]
    thief = before["distractors"][0]["desc"] if before["distractors"] else "competing elements"
    return {
        "baseline_score": baseline,
        "final_score": final,
        "delta": round(final - baseline, 4),
        "brand_brief": brief,
        "competitive_insights": insights,
        "heatmap_before": before["heatmap_png"],
        "heatmap_after": after["heatmap_png"],
        "variant_png": dg.to_data_url(variant),
        "rationale": f"Reduced the {thief} and {directive}, pulling attention toward the target.",
        "iterations": steps,
    }
