"""The Director — orchestrates the agent fleet (Insider → Scout → Eye → Retoucher →
Judge → Eye) and returns an AgentsResult-shaped dict (see the frozen contract).

The pipeline is composed as a LangChain LCEL chain (so LangChain orchestrates the
steps; no API key needed), with a plain sequential fallback so the app runs even
without LangChain installed. LangSmith tracing is optional and self-enables only when
a LangSmith key is set. The Retoucher's branching search (branch.py) optimizes a
Judge-gated fitness: DeepGaze attention, but variants the LLM-judge finds off-brand or
garish are penalized so they can't win on raw attention alone (anti reward-hacking).
"""
from __future__ import annotations

import concurrent.futures as cf

from PIL import Image

import branch
import competitive
import deepgaze_runner as dg
import gemini
from config import settings


# Per-brand caches: briefs + competitor tactics don't change between clicks, so the
# first run pays the Gemini/Pinecone cost and every later run on that brand is instant.
_BRIEF_CACHE: dict[str, dict] = {}
_SCOUT_CACHE: dict[str, dict] = {}


def insider(brand: str) -> dict:
    """Insider agent — our-brand brief (cached per brand; real Gemini call on first use)."""
    key = brand.strip().lower()
    if key not in _BRIEF_CACHE:
        _BRIEF_CACHE[key] = gemini.brand_brief(brand)
    return _BRIEF_CACHE[key]


def scout(brand: str, brief: dict) -> dict:
    """Scout agent — competitor tactics via Pinecone RAG (cached per brand)."""
    key = brand.strip().lower()
    if key not in _SCOUT_CACHE:
        _SCOUT_CACHE[key] = competitive.scout(brand, brief)
    return _SCOUT_CACHE[key]


def _directive_pool(before: dict, insights: dict, brand: str) -> list[str]:
    """Diverse edit hypotheses, spanning safe→moderately strong. ENHANCEMENT-first so the
    winner looks like a *better ad*, not a scorched background with a floating logo; the
    Judge-gated fitness (_make_scorer) penalizes any variant that crosses into garish, so
    the search can push moderately without an ugly edit winning on raw attention."""
    target = f"the {brand} logo and product"
    # Content-level levers that actually move DeepGaze (gentle re-lighting barely does). The first
    # three run on the live (depth=1) path, so they're the highest-value, most distinct edits:
    # de-clutter, reframe head-on, add brand text. Judge-gated fitness still vetoes un-ad-like edits.
    pool = [
        f"make SEVERAL coordinated changes at once to turn this into a polished campaign: remove the "
        f"clutter and any objects, hands, props or stray text crowding or blocking {target}; reframe "
        f"it head-on and enlarge it as the clear hero; clean and simplify the background; and add a "
        f"bold, legible on-brand headline, call-to-action and wordmark on {target}",
        f"remove or clean away any objects, hands, props or background obstructions that crowd or "
        f"block {target} so the product is fully visible, unobstructed, and the clear hero of the shot",
        f"reframe {target} to a clean, head-on, front-facing hero angle — square it to the camera so "
        f"it faces the viewer directly and reads instantly — keep it in roughly the same spot",
        f"add a bold, legible, on-brand headline and call-to-action and strengthen the logo/wordmark "
        f"right at {target} as a strong, high-contrast focal point",
        f"clearly enlarge, brighten and sharpen {target} so it becomes the single biggest, boldest "
        f"focal element while gently dimming and de-cluttering the surroundings — a polished, real ad",
        f"recolor the background to a clean, on-brand solid or subtle gradient so {target} stands out "
        f"as the hero, keeping the shot photographic and realistic",
    ]
    # Targeted suppression of each named competing element (clearly tone down, not blackout).
    pool += [f"clearly tone down or remove the {d['desc']} — it is stealing attention from "
             f"{target}; reduce its brightness, color and prominence so the brand wins the eye"
             for d in before["distractors"]]
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


def _make_scorer(target: list, brand: str, judged: dict[int, dict]):
    """Retoucher fitness = DeepGaze attention, GATED by the LLM-judge. Variants that
    score below the brand-fit gate are scaled down proportionally so a garish, high-
    attention but off-brand edit can't win on attention alone. Per-variant verdicts are
    recorded in `judged` (keyed by image id) for the result + the Judge step."""
    def _score(variant: Image.Image) -> float:
        att = dg.score_only(variant, target)
        if not settings.use_judge:
            return att
        quality, reason = gemini.judge(variant, brand)
        gate = settings.judge_gate
        vetoed = quality < gate
        judged[id(variant)] = {"judge": round(quality, 3), "reason": reason, "vetoed": vetoed}
        return round(att * quality / gate, 4) if vetoed else att
    return _score


def _judge_summary(winner: dict | None, n_vetoed: int) -> str:
    base = f"approved winner (brand-fit {winner['judge']})" if winner else "kept original"
    if n_vetoed:
        base += f"; vetoed {n_vetoed} off-brand variant(s)"
    return base[:110]


# --- Director steps (each takes & returns the run state dict; composed below) -------
def _step_prep(state: dict) -> dict:
    """Insider brief + target detection (concurrent), then the baseline Eye reading."""
    image, brand, target = state["image"], state["brand"], state["target"]
    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        f_brief = ex.submit(insider, brand)
        f_target = ex.submit(gemini.detect_target, image) if target is None else None
        state["brief"] = f_brief.result()
        if f_target is not None:
            target = f_target.result()
    state["target"] = target
    state["before"] = dg.predict(image, target)
    state["baseline"] = state["before"]["attention_score"]
    return state


def _step_context(state: dict) -> dict:
    """Distractor naming + competitor RAG (Scout) — independent, run concurrently."""
    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        f_names = ex.submit(gemini.label_distractors, state["image"], state["before"]["distractors"])
        f_insights = ex.submit(scout, state["brand"], state["brief"])
        f_names.result()
        state["insights"] = f_insights.result()
    return state


def _step_optimize(state: dict) -> dict:
    """Retoucher: branching tree-search over edits, scored by the Judge-gated fitness."""
    pool = _directive_pool(state["before"], state["insights"], state["brand"])

    def propose(_img, node, n):
        start = (node["depth"] * n) % len(pool)  # rotate so each round tries fresh avenues
        return (pool[start:] + pool[:start])[:n]

    judged: dict[int, dict] = {}
    state["result"] = branch.search(
        state["image"], state["baseline"], propose,
        edit=lambda img, directive: gemini.edit_image(img, directive),
        score=_make_scorer(state["target"], state["brand"], judged),
        breadth=settings.breadth, max_depth=state["depth"], beam_width=1,
        target_score=settings.target_score, epsilon=settings.epsilon,
    )
    state["judged"] = judged
    return state


def _step_finalize(state: dict) -> dict:
    """Final Eye reading + assemble the AgentsResult dict (incl. the Judge step)."""
    before, result, judged = state["before"], state["result"], state["judged"]
    brand, brief, insights, target = state["brand"], state["brief"], state["insights"], state["target"]

    best_img = result["best_image"]
    after = dg.predict(best_img, target) if result["improved"] else before
    final = after["attention_score"]
    baseline = state["baseline"]
    thief = before["distractors"][0]["desc"] if before["distractors"] else "competing elements"
    n_variants = sum(1 for n in result["tree"] if n["parent"] is not None)
    n_vetoed = sum(1 for v in judged.values() if v["vetoed"])
    winner = judged.get(id(best_img))

    steps = [
        {"agent": "Insider", "status": "done", "summary": f"{brand}: {brief.get('tone', '')}"[:90]},
        {"agent": "Scout", "status": "done",
         "summary": insights["tactics"][0]["tactic"] if insights.get("tactics") else "no tactics"},
        {"agent": "Eye", "status": "done", "summary": f"baseline {round(baseline * 100)}% on target"},
        {"agent": "Retoucher", "status": "done",
         "summary": f"explored {n_variants} edits across {result['rounds']} rounds"},
        {"agent": "Judge", "status": "done", "summary": _judge_summary(winner, n_vetoed)},
        {"agent": "Eye", "status": "done", "summary": f"best {round(final * 100)}% on target"},
    ]

    state["output"] = {
        "baseline_score": baseline,
        "final_score": final,
        "delta": round(final - baseline, 4),
        "judge_score": winner["judge"] if winner else None,
        "brand_brief": brief,
        "competitive_insights": insights,
        "heatmap_before": before["heatmap_png"],
        "heatmap_after": after["heatmap_png"],
        "variant_png": dg.to_data_url(best_img),
        "rationale": (f"Explored {n_variants} edits in a branching search; kept the variant the "
                      f"Judge approved that best reduced the {thief} and raised attention on the target."),
        "tree": _serialize_tree(result["tree"]),
        "iterations": steps,
    }
    return state


_STEPS = [(_step_prep, "Prep"), (_step_context, "Insider+Scout"),
          (_step_optimize, "Retoucher+Judge"), (_step_finalize, "Finalize")]


def _build_director():
    """Compose the steps as a LangChain LCEL chain so LangChain orchestrates the run
    and LangSmith traces each agent step. Returns (runnable_or_callable, is_langchain).
    Falls back to a plain sequential callable if LangChain isn't available."""
    if settings.use_langchain:
        try:
            from langchain_core.runnables import RunnableLambda
            chain = None
            for fn, name in _STEPS:
                step = RunnableLambda(fn).with_config(run_name=name)
                chain = step if chain is None else chain | step
            return chain, True
        except Exception:
            pass

    def _plain(state: dict) -> dict:
        for fn, _ in _STEPS:
            state = fn(state)
        return state
    return _plain, False


def run(image: Image.Image, brand: str = "the brand", target: list | None = None,
        depth: int = 1) -> dict:
    """Optimize an ad. Pass the brand's `target` box (normalized [x,y,w,h]) when known —
    a curated box gives a meaningful baseline; auto-detection is a noisy fallback.
    LIVE path uses depth=1; depth>1 runs the full tree-search (precompute the showcase).
    Never regresses — the original is the floor."""
    state = {"image": image, "brand": brand, "target": target, "depth": depth}
    director, is_langchain = _build_director()
    if is_langchain:
        state = director.invoke(state, config={
            "run_name": "Pixel Director",
            "metadata": {"brand": brand, "depth": depth},
        })
    else:
        state = director(state)
    return state["output"]
