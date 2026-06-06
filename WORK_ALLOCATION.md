# Work Allocation — 2 people / 2 lanes

> Simplified from 3 instances → 2: the agent layer merged into the backend (one instance can't juggle three lanes). Each lane OWNS a directory. Coordinate only through the frozen API contract below. Commit + push small and often; **pull/rebase before every push**. No keys in git — backend secrets in `backend/.env`, frontend in `frontend/.env.local` (both git-ignored).

## The split (own your directory, don't touch the other's)

### 🟦 BACKEND — Vision spine + Agents + Memory  *(me, this instance; you drive)*
**Owns:** all of `backend/`
- **Vision** (`deepgaze_runner.py`): DeepGaze IIE heatmap + `attention_in_box` score + scanpath, with the dimension-fix helpers and a demo-safe fallback saliency. The money-shot truth engine.
- **Edit/judge** (`gemini.py`): `edit_image` (localized prompt + align + integrity), `detect_target`, LLM-as-judge.
- **Agents** (`agents.py`): the Director loop (Insider, Scout, Eye, Retoucher) + later `branch.py` (beam search + Judge).
- **Memory** (`pinecone_store.py`): seed ~20 competitor ads + RAG for Scout. **LangSmith**: `attention_score` feedback chart.
- **API** (`main.py`): `POST /predict`, `/edit`, `/agents` (+ `/health`).
- See `tasks/workplan-backend.md` for the chunked to-do.

### 🟨 FRONTEND — Interface / Visuals / Voice / Auth  *(your friend)*
**Owns:** all of `frontend/`
- Vite + React + React Flow: upload → heatmap overlay → **before/after wipe** → **animated score counter** → **agent-pipeline canvas** → scanpath nodes → Web Speech voice. Clerk auth (optional, must not block boot).
- Builds against `frontend/src/mock.json` first; flips `USE_MOCK=false` to hit live endpoints via the Vite proxy — **never blocked on backend.**
- See `tasks/workplan-C.md` for the full frontend plan.

---

## Frozen API contract (both lanes align here — change only by agreement)

`POST /predict` — multipart `image`, optional `target` (JSON normalized `[x,y,w,h]`)
```json
{ "width": 1024, "height": 768, "attention_score": 0.34,
  "heatmap_png": "data:image/png;base64,...",
  "target_box": [0.1,0.6,0.3,0.2],
  "scanpath": [{"x":0.12,"y":0.08,"order":1}],
  "distractors": [{"region":[0.5,0.1,0.2,0.2],"share":0.38,"desc":"upper-left region"}] }
```
`POST /edit` — multipart `image`, `directive` (string)
```json
{ "variant_png": "data:image/png;base64,...", "edit_description": "...", "width": 1024, "height": 768 }
```
`POST /agents` — multipart `image`, `brand` (synchronous; returns full result when the loop finishes)
```json
{ "baseline_score": 0.12, "final_score": 0.41, "delta": 0.29,
  "brand_brief": {...}, "competitive_insights": {"tactics":[...]},
  "heatmap_before": "data:...", "heatmap_after": "data:...",
  "variant_png": "data:...", "rationale": "…",
  "iterations": [ {"agent":"Scout","status":"done","summary":"…"} ] }
```
> `/agents` is **synchronous** → the canvas replays `iterations[]` client-side (timed reveal), no streaming. Source of truth: `backend/schemas.py` + `frontend/src/mock.json` (keep in sync).

## Env layout
- `backend/.env` (git-ignored, real keys) ← copy of `backend/.env.example`. Loaded by `config.py`.
- `frontend/.env.local` (git-ignored) ← copy of `frontend/.env.example`. Holds `VITE_CLERK_PUBLISHABLE_KEY` (friend adds) + `VITE_API_BASE`.

## Dependency order
1. **Backend** ships `/predict` (real heatmap+score) → unblocks the spine + frontend's real wiring. (`/predict`, `/edit`, `/agents` already return contract-shaped data on a fallback saliency, so the frontend can flip to live *now*.)
2. **Backend** swaps the fallback for real DeepGaze, then real Insider/Scout (Pinecone), then branching.
3. **Frontend** builds the whole UI on `mock.json`; flips each panel to live as endpoints firm up.
