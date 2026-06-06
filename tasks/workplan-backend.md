# Workplan — Backend (vision spine + agents + memory)

> My lane (this instance). Owns all of `backend/`. Friend owns `frontend/`. Clean + minimal: each module has one job; no speculative abstractions. Demo-safe by design — the server runs and returns contract-shaped data even before heavy deps (torch) or keys are present, so the frontend is never blocked.

## Module map (why each exists)
| File | Responsibility |
|---|---|
| `config.py` | Load `backend/.env`; expose `settings` (keys, pinned model ids, beam params). One source of config. |
| `schemas.py` | Pydantic models = the frozen contract. Keep in sync with `frontend/src/mock.json`. |
| `deepgaze_runner.py` | Vision: density (DeepGaze IIE or fallback) → heatmap, attention-on-target score, distractors, scanpath. Holds the dimension-fix helpers (`align_to_input`, `attention_in_box`, `integrity_ok`). |
| `gemini.py` | `edit_image` (localized edit + align + integrity), `detect_target` (bbox), `judge` (LLM-as-judge). Degrades gracefully with no key. |
| `agents.py` | Director single-variant loop (Insider → Scout → Eye → Retoucher → Eye re-score). |
| `main.py` | FastAPI: `/predict`, `/edit`, `/agents`, `/health` + CORS for the Vite dev server. |
| `branch.py` *(later)* | Beam search (BREADTH=3, greedy) + Judge scoring. Stretch. |
| `pinecone_store.py` *(later)* | Seed ~20 ads + RAG for the real Scout. |

## The loop (what `/agents` does)
`detect target → baseline gaze (score + heatmap) → Insider brief → Scout tactics → Director composes ONE directive (kill top distractor + apply top tactic) → Retoucher edits via Gemini → re-score → return before/after + iterations[] + rationale.`

## Chunks / to-do
### ✅ Chunk 1 — Skeleton + contract (DONE)
- [x] `config.py`, `schemas.py`, `requirements.txt`, CORS, `/health`.
- [x] `main.py` wires `/predict` `/edit` `/agents` to real modules.

### ✅ Chunk 2 — Vision spine w/ fallback (DONE, fallback active)
- [x] `deepgaze_runner.predict`: density → heatmap data URL + attention score + distractors + scanpath.
- [x] Dimension-fix helpers in place.
- [ ] **Activate real DeepGaze IIE**: `pip install torch (cpu) + git+DeepGaze`, download MIT1003 centerbias, replace the `_density` fallback branch. Verify output dims handled.
- [ ] DeepGaze III scanpath (replace greedy-peak proxy). *(stretch)*

### ✅ Chunk 3 — Gemini edit/detect/judge (DONE, no-key fallback)
- [x] `edit_image` localized template + align + (integrity hook).
- [ ] **Smoke-test a real edit** once `GEMINI_API_KEY` env loads; confirm output image parses + re-aligns; wire `integrity_ok` reject/redo.

### Chunk 4 — Real brains
- [ ] `agents.insider`: real Gemini brand brief.
- [ ] `pinecone_store.py` seed ~20 ads (Gemini analysis → upsert) + `data/competitors/*.md`.
- [ ] `agents.scout`: real Pinecone RAG → tactics + `scout_brief.md`.

### Chunk 5 — Observability
- [ ] LangSmith tracing + `attention_score` run feedback (rising-score chart).

### Chunk 6 — Branching (stretch, only if 1-variant loop is solid)
- [ ] `branch.py`: greedy beam search, dual fitness (0.6 DeepGaze + 0.4 judge), multi-criteria stop.
- [ ] Emit branch tree in `/agents` for the canvas.
- [ ] Precompute a hero run as a live-demo fallback.

## Run
```
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
`GET /health` shows whether Gemini/Pinecone keys loaded. Frontend proxies to `:8000`.
