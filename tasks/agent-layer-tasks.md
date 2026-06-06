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

## Coordination note — how the canvas gets live node status (B ↔ C)
`POST /agents` is **synchronous**: per the frozen contract it returns the full result (including `iterations: [{agent, status, summary}]`) only when the whole loop finishes. So the canvas "light-up" (grey → pulsing → green) should **replay `iterations[]` client-side** after the response lands (a timed reveal), NOT assume live server push. This keeps B simple (no SSE/websocket infra) and the demo reliable. If true live streaming is wanted later, B adds a stretch `GET /agents/stream` (SSE) — but **only after the synchronous path is solid. Confirm the replay approach with C so C doesn't wait on streaming that isn't coming.**

---

## Coordination note — `/agents` stage latency: edits now run concurrently (C → B) ✅ DONE
C profiled the wired `/agents` and found it **edit-bound**: each `gemini.edit_image` (image-gen ~5–12s) was the per-edit bottleneck, and with `branch.py` now on the live path a full search is breadth 3 × depth 3 ≈ **9 sequential edits ≈ 2–5 min** — too slow to run live.
**Fix applied in `branch.py`** (B and C converged on the same change independently; B's landed first): each round expands the frontier into independent `(parent, directive)` jobs and runs `edit`+`score` **concurrently** via `cf.ThreadPoolExecutor(max_workers=min(8, len(jobs)))`. `ex.map` preserves submission order, so **node ids and the emitted tree are byte-for-byte identical to the serial version** — the canvas/branch view is unaffected. Verified ~3× wall-clock speedup per round and unchanged self-test output. Net: a round's edits cost ~1 edit of wall time instead of `breadth`.
Still recommended for stage: **pre-warm DeepGaze** before demos, and **precompute a hero run** as the fallback (Phase 3). If `breadth`/`beam_width` grow, revisit the parallel cap and Gemini rate limits.

---

## Coordination note — Scout now does LIVE web search (C → B) ✅ DONE
Previously Scout retrieved only from a static 12-ad corpus (`pinecone_seed.ADS` → `kb.json` → Pinecone) — the "evidence" was hand-curated, never real. Added a **live web-grounding layer** in `competitive.py` so Scout pulls **real, current** competitor campaigns:
- New `_retrieve_web(brand, brief, fam, k)` calls Gemini with the **Google Search tool** (`types.Tool(google_search=types.GoogleSearch())`) and parses a JSON array of rival ad analyses. `_grounding_meta()` extracts the real **source URLs + search queries** Gemini used.
- `scout()` cascade is now **web → Pinecone → curated KB**, with the KB **padding** thin web results so synthesis always has ≥k items. Verified live (Liquid Death → Waterloo/Olipop/Poppi + bevnet/marketingdive sources).
- **Return shape extended (backward-compatible):** still `{"tactics", "source"}`, plus `"sources":[{title,url}]` and `"queries":[...]`. These flow through `/agents` → `competitive_insights`, so the **frontend can show "grounded on N live sources"** as demo proof. The `runs/scout_*.md` artifact now lists the queries + sources too.
- **Toggle:** `WEB_SEARCH=0` disables it (config `web_search`); `web_k=4`. Requires `GEMINI_API_KEY` (no new deps — uses the existing `google-genai`).
- **Latency:** Scout now makes **2 Gemini text calls** (grounded retrieve + synthesize), once per `/agents` run (~+3–8s). Not in the per-edit loop, so it doesn't multiply. `config.py` + `competitive.py` are B's files — flagging the cross-edit; revert/adjust freely.

---

## Coordination note — Judge wired into fitness + LangChain orchestration (C → B) ✅ DONE
Two Phase-2/3 items wired in `agents.py` (+ `config.py`, `requirements.txt`):
- **Judge (LLM-as-judge) now gates the Retoucher's fitness.** `_make_scorer()` scores each variant as DeepGaze attention, but if `gemini.judge(variant, brand)` returns brand-fit below `settings.judge_gate` (0.45) the score is scaled down proportionally — so a **garish, high-attention but off-brand variant can't win on attention alone** (the anti-reward-hacking pillar). The headline `baseline_score`/`final_score` stay **pure DeepGaze** (re-derived via `dg.predict`), so the demo number is honest. Adds a **"Judge"** step to `iterations[]` and a `judge_score` field to the result. Per-variant verdicts recorded by image id. Verified: attention 0.60 garish → fitness 0.27, loses to a clean 0.40. Toggle `JUDGE=0`. Latency: 1 judge call per scored variant, but it runs *inside* the round's thread pool (alongside the edit), so ~+1 judge of wall time per round, not per variant.
- **LangChain now orchestrates the Director.** The pipeline is refactored into 4 step fns (`_step_prep`/`_context`/`_optimize`/`_finalize`) composed as an **LCEL chain** (`RunnableLambda | … .invoke()`) — load-bearing, **needs no API key / network**. Plain sequential fallback if `langchain-core` is absent (`_build_director` returns `(callable, False)`), so the app never breaks. Toggle `LANGCHAIN=0`.
- **LangSmith tracing is optional** (observability only — NOT needed for orchestration). `config.py` now auto-disables `LANGCHAIN_TRACING_V2` when no LangSmith key is present, to kill the 401-on-every-run spam. Drop a `LANGCHAIN_API_KEY` in `.env` later and tracing self-enables (the rising-score chart). `requirements.txt`: added `langchain-core` (pulls langsmith transitively).
- `agents.py`/`config.py`/`requirements.txt` are B/A files — flagging; revert/adjust freely.

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
