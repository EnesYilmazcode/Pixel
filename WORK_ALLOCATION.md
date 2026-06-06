# Work Allocation — 3 Claude Code instances

> Each instance OWNS distinct files. Coordinate only through the frozen API contract below. Commit + push small and often; **pull/rebase before every push** (3 agents are live in this repo). No API keys in git — they live in `.env` (git-ignored); `.env.example` lists the names.

## The split (own your files, don't touch the others')

### 🟦 Instance A — Core Spine / Vision  *(the money shot — critical path)*
**Owns:** `backend/deepgaze_runner.py`, `backend/gemini.py`, `backend/main.py`, `backend/requirements.txt`, `backend/models/`
- `deepgaze_runner.py`: DeepGaze IIE heatmap + `attention_in_box` score; DeepGaze III scanpath (stretch). Load models ONCE at startup. Includes the dimension-fix helper (PLAN.md → Critical Build Risk).
- `gemini.py`: `edit_image(image, directive)` with localized-edit prompt + `align_to_input` + integrity gate.
- `main.py`: FastAPI app + `POST /predict`, `POST /edit`. Mount the agents router (owned by B) with one `include_router` line.
- Download centerbias + pin `gemini-2.5-flash-image`.
- **Start NOW. Get `/predict` returning a real heatmap+score on a sample ad ASAP, then `/edit`.** This is the demo spine.

### 🟩 Instance B — Agent Layer + Memory
**Owns:** `backend/agents.py`, `backend/competitive.py`, `backend/pinecone_seed.py`, `backend/routes_agents.py`
- LangChain **Director** orchestrating the 6 agents (Insider, Scout, Eye, Retoucher, Judge — see PLAN.md fleet). Sub-agents are Tools, loop is plain Python.
- Pinecone: `pinecone_seed.py` seeds ~20 competitor/past ads as Gemini-analysis text + metadata; `competitive.py` does the RAG query → `CompetitiveInsights`.
- LangSmith: set `LANGCHAIN_*` env, log `attention_score` as run feedback (the rising-score chart).
- `routes_agents.py`: `POST /agents` returning the full result object (contract below). A imports this router into `main.py`.
- **Can start immediately:** Pinecone seeding is independent. Stub `score_gaze`/`edit_image` (mock) until A's functions land, then import the real ones.

### 🟨 Instance C — Frontend + Demo Visuals + Voice  *(me, this instance)*
**Owns:** all of `frontend/`, plus `.env.example`
- Vite + React + React Flow. Upload → image + **heatmap overlay** → **before/after wipe slider** → **animated score counter** → **React Flow agent-pipeline canvas** (consumes `/agents`) → scanpath nodes → **Web Speech voice**.
- Builds against `frontend/src/mock.json` (matches the contract) first; flips to real endpoints via Vite proxy as they come online — **never blocked on backend.**
- Demo polish: loading states per agent node, distractor callout, hero-ad Mode-A path.

**Humans:** drive one instance each (you: A or C + this planning instance; teammate: B). Reassign freely — just keep one owner per file set.

---

## Frozen API contract (all 3 align here — change only by agreement)

`POST /predict` — multipart `image`, optional `target` (normalized `[x,y,w,h]`)
```json
{ "width": 1024, "height": 768, "attention_score": 0.34,
  "heatmap_png": "data:image/png;base64,...",
  "target_box": [0.1,0.6,0.3,0.2],
  "scanpath": [{"x":0.12,"y":0.08,"order":1}],
  "distractors": [{"region":[0.5,0.1,0.2,0.2],"share":0.38,"desc":"model face"}] }
```
`POST /edit` — multipart `image`, `directive` (string)
```json
{ "variant_png": "data:image/png;base64,...", "edit_description": "boosted CTA contrast",
  "width": 1024, "height": 768 }
```
`POST /agents` — multipart `image`, `brand`, optional `target`
```json
{ "baseline_score": 0.34, "final_score": 0.51, "delta": 0.17,
  "brand_brief": {...}, "competitive_insights": {"tactics":[...]},
  "heatmap_before": "data:...", "heatmap_after": "data:...",
  "variant_png": "data:...", "rationale": "…",
  "iterations": [ {"agent":"Scout","status":"done","summary":"…"} ] }
```
Internal function signatures (so A↔B don't churn): `score_gaze(image_path, target_region) -> GazeReport`; `edit_image(image_path, directive) -> variant_path`.

## Dependency order
1. **A** ships `/predict` (real heatmap+score) → unblocks the spine + C's real wiring.
2. **B** seeds Pinecone (now, independent) + builds Director against mocked `score_gaze`/`edit_image`, swaps to A's real fns once `/predict`+`/edit` exist.
3. **C** builds the whole UI on `mock.json` from minute one; flips each panel to live as A/B endpoints land.
