# Tasks — Agent Layer + Memory (Director, fleet, Pinecone, LangSmith)

> For the instance building the agent backend. **Owns only these files** — do NOT touch `frontend/` or the vision spine files (`deepgaze_runner.py`, `gemini.py`):
> `backend/agents.py`, `backend/competitive.py`, `backend/pinecone_seed.py`, `backend/routes_agents.py`, `backend/branch.py`, `backend/config.py`
> Coordinate only via the frozen contract in [WORK_ALLOCATION.md](../WORK_ALLOCATION.md). Commit small + often; **pull/rebase before every push**.

**Dependency rule:** the vision functions `score_gaze(image_path, target)` and `edit_image(image_path, directive)` are owned by the spine instance. **Mock them first** (return canned values), build the whole loop, then swap to the real imports once they land. You are never blocked.

---

## Design reference (build to this)

### Scout — how competitive analysis works (two layers)
**Layer 1 — Knowledge base (offline, run once):** `pinecone_seed.py`
- Ingest ~20–40 real competitor + own past ads. For each: a Gemini vision call analyzes it (layout, color, CTA placement, what works/doesn't) → store the **analysis text** + metadata `{brand, competitor, year, tactics[]}` in Pinecone index `pixel-ads`.
- Also dump a human-readable `data/competitors/<brand>.md` per brand — this is the "write findings to files so we understand them" part, and doubles as a demo artifact.

**Layer 2 — Per run:** `competitive.py::scout(brand, brand_brief)`
1. Query Pinecone with brand/product/competitor terms → top-k analyses.
2. Gemini synthesizes **3–5 tactics** `{tactic, evidence, apply}` relevant to *this* ad.
3. Write `runs/<job_id>/scout_brief.md` (debug + demo artifact) **and** return the `CompetitiveInsights` JSON.

➡️ Pinecone is the persistent memory; the per-run JSON is what the Director actually consumes. The `.md` files are for humans/demo, not the pipeline's source of truth.

### Retoucher branching — beam search with dual scoring (your recursive idea, formalized)
Yes, your plan (4–5 branches, score each, recurse, stop at a threshold) is good. It's **greedy beam search**. Recommended params (in `config.py`, tunable):

| Param | Value | Why |
|---|---|---|
| `BREADTH` (branches/round) | **3** live (4–5 only if precomputed) | enough diversity to *look* like exploration without 5× the cost/latency |
| `MAX_DEPTH` (rounds) | **3** | hard cap → bounded runtime on stage |
| `BEAM_WIDTH` (kept/round) | **1** (greedy) | keeps cost linear: total edits ≈ BREADTH×DEPTH ≈ 9, not exponential |
| `TARGET` | **0.40** attention-on-target | early-success stop |
| `EPSILON` | **0.02** | diminishing-returns stop |

**Per round (`branch.py`):**
1. **Director proposes `BREADTH` *diverse* edit directives** from current best + gaze gaps + Scout tactics (e.g. "dim the face thief", "boost CTA contrast", "move logo to scanpath endpoint"). Diversity is the point — each branch tests a different hypothesis.
2. **Retoucher applies each** via `edit_image` in parallel → variants (with `align_to_input` + integrity gate from PLAN.md).
3. **Eye scores each** → DeepGaze `attention_on_target` (objective).
4. **Judge scores each** → Gemini LLM-as-judge: quality / brand-fit / "would this run as a real ad" (0–1) + reason.
5. **Fitness** = `0.6 * deepgaze_norm + 0.4 * judge_score` − penalties (brand-rule violation, integrity fail). **The Judge is essential** — DeepGaze alone can be gamed (a giant garish logo scores high attention but looks terrible); the LLM judge stops that reward-hacking. Validate: this dual signal is exactly what makes the result credible.
6. Keep top `BEAM_WIDTH` as the new current; record the branch tree.

**Stop when ANY:** `depth ≥ MAX_DEPTH` **or** `best_fitness_delta < EPSILON` **or** `attention ≥ TARGET` **or** no branch beat the current best. (Max-depth is the safety net so it never loops forever live.)

**Output:** a tree `[{round, variants:[{img, deepgaze, judge, fitness, directive}], chosen}]` → feeds the React Flow branch view + the LangSmith rising-score curve.

**Build order:** get the **single-variant loop** working first (`BREADTH=1, MAX_DEPTH=1`), prove the number moves, THEN turn on branching. Don't build Judge/branching until the 1-variant loop is green.

---

## Task breakdown (small, sequenced, non-interfering — check off as you go)

### Phase 1 — Single-variant loop (do first)
- [ ] `config.py`: params above + model ids + env loading (`GEMINI_API_KEY`, `PINECONE_*`, `LANGCHAIN_*`).
- [ ] `agents.py`: define the 5 MVP tools with **mock returns** matching the data contract (`analyze_brand`, `competitive_insights`, `score_gaze`, `edit_image`, + Director).
- [ ] `agents.py`: Director loop = baseline gaze → one directive → one edit → re-score (BREADTH=1).
- [ ] `routes_agents.py`: `POST /agents` returns the full result object (contract). Hand the spine instance the one `include_router` line for `main.py`.
- [ ] Smoke-test `/agents` end-to-end on mocks (frontend can already animate against it).

### Phase 2 — Real brains
- [ ] `pinecone_seed.py`: seed ~20 ads (Gemini analysis → upsert) + dump `data/competitors/*.md`. (Independent — can start now.)
- [ ] `competitive.py`: real Scout (Pinecone query → Gemini synthesize → `scout_brief.md` + JSON).
- [ ] `analyze_brand`: real Insider (one Gemini call → BrandBrief).
- [ ] Swap mocked `score_gaze`/`edit_image` → import the spine instance's real functions.
- [ ] LangSmith: set env, log `attention_score` as run feedback (the rising-score chart).

### Phase 3 — Branching (stretch — only if Phase 1–2 green)
- [ ] `branch.py`: beam search per design above (BREADTH=3, greedy, multi-criteria stop).
- [ ] `Judge`: Gemini LLM-as-judge scoring variants (0–1 + reason).
- [ ] Emit the branch tree in `/agents` so the canvas can draw it.
- [ ] Tune BREADTH/DEPTH for live latency; precompute a hero run as fallback.
