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
### ✅ DONE & verified on real ads
- [x] Skeleton + contract: `config.py`, `schemas.py`, CORS, `/health`, `main.py` routes.
- [x] **Real DeepGaze IIE** (GPU) → heatmap + attention score + distractors + scanpath (+ Gaussian/MIT1003 centerbias, downscale-for-speed). Demo-safe fallback if torch absent.
- [x] **Real Gemini** edit/detect/judge — **hardened** against empty/blocked responses (no crash on branded ads).
- [x] **Named distractors** via Gemini vision ("woman's face" not "upper-left region").
- [x] **Insider** (real brand brief) + **Scout** (real Pinecone RAG, 11 ads seeded). `/agents` 500 (list-tone) **fixed**.
- [x] **Branch tree-search** (`branch.py`): branches die/grow, never regresses; parallel edits. Live = depth-1 flat; deep = precompute.
- [x] **Parallel** intake + edits → live `/agents` ~25-30s.
- [x] **Campaign save/resume**: `storage.py` + `/campaigns` CRUD + `/campaigns/{id}/optimize`.

### 🔴 NOW — make the lift actually compelling (the money shot is weak)
Real-ad test: red-bull 10→11%, spotify 11→11%, apple 53→54% — only **+1 pt**. Edits aren't moving DeepGaze attention enough.
- [ ] Stronger, target-aware directives (e.g. "dim everything except the logo region to 50%", explicit reframing) — edits DeepGaze visibly responds to.
- [ ] Score against a **tight** target box (logo), not a broad region, so there's headroom + a bigger relative lift.
- [ ] Use deep branching (depth 3) to **precompute** a hero run with a real lift → cache as the demo showcase.
- [ ] Pick the 1-2 sample ads with the best baseline→lift story; record them.

### ⬜ Next
- [ ] LangSmith tracing + `attention_score` chart.
- [ ] Integrity gate + re-detect target after edit (correctness).
- [ ] DeepGaze III scanpath (replace greedy-peak proxy). *(stretch)*

## Run
```
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
`GET /health` shows whether Gemini/Pinecone keys loaded. Frontend proxies to `:8000`.
