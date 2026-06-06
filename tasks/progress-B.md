# Progress — Instance B (Agent Layer + Memory)

> Live status so other instances don't overlap. Updated as I go. **Last update: ~12:25 PM.**

## ✅ Done (pushed)
- **`backend/competitive.py` — Scout** (`6e6d488`). `scout(brand, brief) -> {"tactics":[{tactic,evidence,apply}], "source":...}`.
  - Retrieval: Pinecone (when keys+SDK) → **local `kb.json` fallback** → built-in list. Gemini synthesizes 3 brand-specific tactics; templated fallback with no key. Writes `runs/scout_<brand>.md` per run.
  - Verified offline on Coca-Cola → 3 grounded tactics citing Pepsi/Dr Pepper/McDonald's.
- **`backend/pinecone_seed.py` — memory seed** (`6e6d488`). 12 curated competitor-ad analyses → Pinecone (when keyed) + **always writes** `data/competitors/*.md` briefs + `kb.json` (offline KB, committed). Run: `python pinecone_seed.py`.
- **`data/competitors/*.md` + `kb.json`** committed — demo prop ("research written to files") + Scout's offline source.

## 🔌 Integration handoff (NOT done — needs the agents.py owner)
- `agents.py` still has a **stub `scout(brand, brief)`**. Swap it for **`from competitive import scout`** — identical signature, drop-in. One line.
- Optional: swap the `insider()` stub for a Gemini-backed brief (I can provide).
- I did **not** edit `agents.py` (spine instance's hot file). Whoever owns it: just add the import + delete the stub. Tracked as task #11.

## 🚧 Mine next — DO NOT take these (avoid overlap)
- **LangSmith** (task #6): tracing env + log `attention_score` as run feedback → rising-score chart. Will live in a small `backend/observability.py` + env (won't touch `agents.py` beyond a decorator/import seam I'll coordinate).
- **Branching + Judge** (task #9, stretch): `backend/branch.py` — greedy beam search (BREADTH=3, MAX_DEPTH=3, beam=1), dual fitness `0.6*deepgaze + 0.4*judge`, multi-criteria stop. Uses A's `gemini.judge`. Self-contained file.

## File ownership (so we don't collide)
- **B touches:** `competitive.py`, `pinecone_seed.py`, `branch.py` (future), `observability.py` (future), `data/competitors/`, `runs/`.
- **B will NOT touch:** `agents.py`, `main.py`, `deepgaze_runner.py`, `gemini.py`, `config.py`, `schemas.py`, all of `frontend/`.

## How another instance can use Scout right now
```python
from competitive import scout
insights = scout("Coca-Cola", brand_brief)   # -> {"tactics": [...], "source": "local-kb"}
```
- No Pinecone needed — `kb.json` makes it work offline. To activate vector search: uncomment `pinecone` in `requirements.txt`, set `PINECONE_API_KEY`, run `python pinecone_seed.py`.
