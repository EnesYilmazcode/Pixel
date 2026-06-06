"""The Director loop — single-variant MVP (baseline → directive → edit → re-score).

Insider/Scout are stubbed here and become real in Phase 2 (Gemini brief + Pinecone
RAG). Branching/Judge (branch.py) layers on top once this 1-variant loop is green.
Returns an AgentsResult-shaped dict (see schemas.py / the frozen contract).
"""
from __future__ import annotations

import concurrent.futures as cf

from PIL import Image

import branch
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


def _directive_pool(before: dict, insights: dict, brand: str) -> list[str]:
    """Diverse, AGGRESSIVE edit hypotheses — gentle nudges don't move DeepGaze; suppressing
    competitors does (verified: +10 pts compounding vs +1 for soft edits)."""
    target = f"the {brand} logo and product"
    pool = [f"strongly darken, blur and desaturate the {d['desc']} so it stops competing for attention"
            for d in before["distractors"]]
    pool += [
        f"mute everything except {target}: darken and desaturate the background and surrounding "
        f"objects so {target} is the single brightest focal point",
        f"boost the contrast, saturation and sharpness of {target} while dimming everything around it",
    ]
    pool += [t["apply"] for t in insights.get("tactics", [])]
    seen, uniq = set(), []
    for d in pool:
        if d and d not in seen:
            seen.add(d)
            uniq.append(d)
    return uniq


def _serialize_tree(tree: list[dict]) -> list[dict]:
    return [{"id": n["id"], "parent": n["parent"], "depth": n["depth"], "score": n["score"],
             "status": n["status"],
             "directive": str(n["directive"])[:80]} for n in tree]


def run(image: Image.Image, brand: str = "the brand", target: list | None = None,
        depth: int = 1) -> dict:
    """Optimize an ad. Pass the brand's `target` box (normalized [x,y,w,h]) when known —
    a curated box gives a meaningful baseline; auto-detection is a noisy fallback.
    LIVE path uses depth=1; depth>1 runs the full tree-search (precompute the showcase).
    Never regresses — the original is the floor."""
    # Stage 1: brand brief (+ target detection only if no curated box was given).
    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        f_brief = ex.submit(insider, brand)
        f_target = ex.submit(gemini.detect_target, image) if target is None else None
        brief = f_brief.result()
        if f_target is not None:
            target = f_target.result()

    before = dg.predict(image, target)
    baseline = before["attention_score"]

    # Stage 2: distractor naming + competitor RAG are independent — run concurrently.
    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        f_names = ex.submit(gemini.label_distractors, image, before["distractors"])
        f_insights = ex.submit(scout, brand, brief)
        f_names.result()
        insights = f_insights.result()

    pool = _directive_pool(before, insights, brand)

    def propose(_img, node, n):
        start = (node["depth"] * n) % len(pool)  # rotate so each round tries fresh avenues
        return (pool[start:] + pool[:start])[:n]

    result = branch.search(
        image, baseline, propose,
        edit=lambda img, directive: gemini.edit_image(img, directive),
        score=lambda variant: dg.score_only(variant, target),
        breadth=settings.breadth, max_depth=depth, beam_width=1,
        target_score=settings.target_score, epsilon=settings.epsilon,
    )

    best_img = result["best_image"]
    after = dg.predict(best_img, target) if result["improved"] else before
    final = after["attention_score"]
    thief = before["distractors"][0]["desc"] if before["distractors"] else "competing elements"
    n_variants = sum(1 for n in result["tree"] if n["parent"] is not None)

    steps = [
        {"agent": "Insider", "status": "done", "summary": f"{brand}: {brief.get('tone', '')}"[:90]},
        {"agent": "Scout", "status": "done",
         "summary": insights["tactics"][0]["tactic"] if insights.get("tactics") else "no tactics"},
        {"agent": "Eye", "status": "done", "summary": f"baseline {round(baseline * 100)}% on target"},
        {"agent": "Retoucher", "status": "done",
         "summary": f"explored {n_variants} edits across {result['rounds']} rounds"},
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
        "variant_png": dg.to_data_url(best_img),
        "rationale": (f"Explored {n_variants} edits in a branching search; kept the variant that "
                      f"best reduced the {thief} and raised attention on the target."),
        "tree": _serialize_tree(result["tree"]),
        "iterations": steps,
    }
