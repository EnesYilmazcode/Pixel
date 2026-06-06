# Pixel — Build Plan

> Architecture spec + technical quickstart + the hour-by-hour timeline. Source of truth for the build. Update it when decisions change.

---

## ⏱️ Timeline (it's ~11:20 AM · demos 3:00 PM · ~3h40m left)

**Verdict: START BUILDING NOW.** Planning is done. The goal for the next hour is a real heatmap on a real image — not more docs.

| Time | What | Owner |
|---|---|---|
| **11:20–11:35** | Scaffold repo (Milestone 0): `backend/`, `frontend/`, `.env.example`, requirements. Split work. | Both |
| **11:35–12:30** | **Track A:** DeepGaze IIE → heatmap + `attention_score` on a sample ad (DERISK #1). **Track C:** Vite + React + React Flow scaffold, image upload, static heatmap overlay. | A: builder 1 · C: builder 2 |
| **12:00** | Lunch served — eat while models download / installs run. | — |
| **12:30–1:15** | **Core loop end-to-end:** upload → heatmap → score → **Gemini edit → re-score** (THE MONEY SHOT). Prove the number moves on ONE hero ad. | Both converge |
| **12:30–1:00** | AMA (Plastic Labs) — optional; one person can half-listen, builds keep running. | — |
| **1:15–2:00** | **Multi-agent layer:** seed Pinecone with ~20 competitor/past ads, Competitive Analysis + Brand agents, LangChain leader loop. React Flow **agent pipeline** that lights up live. | A: agents/Pinecone · C: agent canvas |
| **2:00–2:30** | Integrate + polish. **Precompute hero before/after** and cache to disk (demo fallback). Add Clerk/Sendblue ONLY if green. | Both |
| **2:30–2:50** | 🧊 **FEATURE FREEZE.** Rehearse the demo on the hero ad twice. Verify cached fallbacks work offline. | Both |
| **2:50–3:00** | Final commit + push. Breathe. | Both |
| **3:00–5:00** | Demos. | — |

**Sacred rule:** never cut the before/after attention score — it's the proof.
**Cut order if behind:** Sendblue → Clerk → DeepGaze III scanpath → multi-iteration loop → competitor-corpus depth.

### Demo script (90 seconds)
1. "Brands can't see where attention goes." Upload a Coca-Cola ad.
2. Heatmap + scanpath nodes appear → "37% of attention is wasted on the model's face, only 12% on the can."
3. Hit **Optimize** → agent pipeline lights up (Brand → Competitor → Gaze → Editor). "It checked what Pepsi does well."
4. Edited image appears → re-score → **"attention on the can: 12% → 41%."** Big number on screen.
5. (Stretch) "Approve?" → Sendblue iMessage.

---

## Sponsor Strategy (tiers)

3 well-integrated sponsors already maxes the 15-pt criterion. Extra sponsors = prize eligibility, not more points. Lock the core, add by cheapest-risk-per-prize, never let one derail the demo.

| Tier | Sponsor | Role | When |
|---|---|---|---|
| **1 Core** | **Gemini** | Image editing + agent reasoning (the engine) | Now |
| **1 Core** | **LangChain** | Multi-agent orchestration (= the track) | Now |
| **2 Commit** | **Pinecone** | Competitor-ad memory / RAG → competitive-analysis agent | Once core loop works (~1:15) |
| **3 Polish** | **Clerk** | Drop-in auth / team workspaces (~20 min, low risk) | If green ~2:00 |
| **3 Stretch** | **Gemini Live API** | Voice interface to the optimizer — high wow, needs mic+websockets | Only if core + Pinecone solid (~2:00) |
| **3 Stretch** | **Sendblue** | iMessage the winning variant for approval | Last, if time |
| build tool | **Cursor** | Coding in it — free mention, no work | — |

**Commit to 4 (Gemini, LangChain, Pinecone, Clerk); Gemini Live + Sendblue are stretch.** Never let a stretch sponsor threaten the before/after money shot.

---

## Work Split & Ownership (2 people)

**Own directories, not phases.** Avoids blocking and merge conflicts.

**🔧 Person A — Engine (owns `backend/`)**
1. DeepGaze runner: heatmap + `attention_score` (DERISK FIRST)
2. FastAPI `/predict`, `/edit`, `/agents`
3. Gemini edit wrapper → LangChain leader + agents → Pinecone seed + competitive analysis

**🎨 Person B — Interface (owns `frontend/`)**
1. Vite + React Flow scaffold
2. Upload + image + heatmap overlay
3. Scanpath nodes + live agent-pipeline canvas
4. Before/after score display (the money shot UI)

**🔑 Anti-collision protocol:**
- **First 15 min, together:** lock the **API contract** (endpoints + JSON, from the Data Contract below). Freeze it; change only by mutual agreement.
- Person B builds against a **static mock JSON** so the frontend never waits on the backend.
- Integrate at TWO checkpoints only: **~1:15** wire FE → `/predict` + `/edit`; **~2:00** wire `/agents`.
- Cloud agents take sub-tasks *within* each lane (e.g. A's agent seeds Pinecone while A builds DeepGaze).
- Commit + push small and often; pull before push (see CLAUDE.md).

---

## Architecture Spec

**Goal:** Upload ad image → predict where eyes look (DeepGaze) → agents edit image (Gemini "Nano Banana") to pull attention toward the brand target (logo/CTA) → prove it with a before/after attention score.

### Agent roster
| Agent | Single Responsibility | Inputs | Outputs |
|---|---|---|---|
| **Leader (Orchestrator)** | Run the loop, decide which edit to apply next, decide when to stop. | `image`, `brand`, `target` | `winning_variant`, score history, rationale |
| **Brand Understanding** | Brand brief: product, audience, tone, colors, target to amplify. | `brand`, optional assets | `BrandBrief` |
| **Competitive Analysis** | What competitors/own past ads do well/poorly → "winning patterns." | `brand`, `BrandBrief` | `CompetitiveInsights` (3–5 tactics) |
| **Gaze Analysis** | Run DeepGaze IIE + III, compute attention metric on target. | `image`, `target_region` | `GazeReport` (heatmap, scanpath, score, distractors) |
| **Creative Editor** | Turn insights + gaze gaps into one Gemini edit, apply, re-score. | `image`, briefs, `GazeReport`, `edit_directive` | `variant_image`, `edit_description` |

### Orchestration flow (Leader's sequence)
1. **Intake** — `image` + `brand` + `target` (if target missing, Gemini detects logo/CTA bbox).
2. **Brand brief** (parallel) → `BrandBrief`.
3. **Competitive scan** (parallel, RAG over Pinecone) → `CompetitiveInsights`.
4. **Baseline gaze** → `GazeReport_0` (`baseline_score`, `top_distractors`).
5. **Decide edit** — Leader fuses gaze leaks + competitor tactics + brand constraints into ONE `edit_directive`. *(This is where competitor tactics become concrete edits.)*
6. **Edit** → `variant_image`.
7. **Re-score** → new score.
8. **Loop/stop** — if improved and `iteration < MAX (default 3)` and Δ ≥ 2%, keep best and loop. Else stop.
9. **Report** — best variant, baseline vs final, before/after heatmaps, rationale. *(Stretch: Sendblue.)*

### LangChain wiring (keep simple)
- One `AgentExecutor` as **Leader**; sub-agents exposed as **Tools** (not nested agents). Loop is a plain Python `for`. **No LangGraph** — fixed sequence doesn't need it.
- Tools: `analyze_brand(brand)`, `competitive_insights(brand, brief)`, `score_gaze(image_path, target_region)`, `edit_image(image_path, directive)`.
- Gemini for all reasoning + edits; DeepGaze behind `score_gaze`. Tools are trivial to mock/parallelize.

### Pinecone usage
- **Store (seed before demo):** ~20–40 competitor + own past ads as Gemini-generated analysis text (layout, color, CTA placement, what works) + metadata `{brand, competitor, year, image_url, tactics[]}`. Embed the analysis text. Plus a small set of "winning attention pattern" rules.
- **Query:** Competitive Analysis agent queries `"{brand} {product} ad layout attention CTA"` filtered by brand/competitors → top-k → Gemini summarizes into `CompetitiveInsights`.
- **Index:** single `pixel-ads`, namespace per brand-family (e.g. `cola`).

### MVP vs stretch
- **MVP:** upload + pick brand/target · IIE heatmap + baseline score · Leader → 1 edit → re-score → before/after · Competitive Analysis on ~20 seeded ads · Brand brief (single Gemini call).
- **Stretch (cut first):** DeepGaze III scanpath · multi-iteration loop · Clerk auth · Sendblue approval · large ad corpus.

### Data contract
```json
{
  "job_id": "uuid", "brand": "Coca-Cola", "competitors": ["Pepsi"],
  "image_path": "/uploads/ad.png",
  "target": { "label": "CTA", "bbox": [120,400,300,120] },
  "brand_brief": { "audience": "18-30 urban", "tone": "bold, joyful",
    "palette": ["#F40009","#FFFFFF"], "target_region": [120,400,300,120],
    "dos": ["keep red dominant"], "donts": ["no blue (Pepsi)"] },
  "competitive_insights": { "tactics": [
    { "tactic": "high-contrast CTA", "evidence": "Pepsi 2023", "apply": "boost CTA saturation" } ] },
  "gaze_report": { "iteration": 0, "heatmap_path": "/out/heat_0.png",
    "scanpath": [ { "x": 120, "y": 80, "order": 1 } ],
    "target_attention_score": 0.34,
    "top_distractors": [ { "region": [x,y,w,h], "share": 0.38, "desc": "model face" } ] },
  "edit_directive": "Boost CTA contrast; dim top-right face; move logo to scanpath endpoint.",
  "variant": { "iteration": 1, "image_path": "/out/variant_1.png",
    "edit_description": "CTA saturation +20%, darkened upper-right",
    "target_attention_score": 0.51 },
  "result": { "baseline_score": 0.34, "final_score": 0.51, "delta": 0.17,
    "winning_image_path": "/out/variant_1.png" }
}
```
`target_attention_score` ∈ [0,1] = fraction of predicted fixation mass inside `target_region`. **The single number every agent optimizes and the demo headlines.**

---

## Technical Quickstart

Models load pretrained weights automatically on first call. **Do DeepGaze first — it's the highest risk.**

### 1. DeepGaze setup
```bash
python -m venv .venv && .venv\Scripts\activate          # Windows; or: source .venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu  # CPU is fine
pip install scipy numpy pillow
pip install git+https://github.com/matthias-k/DeepGaze.git   # -> deepgaze_pytorch
```
**Centerbias (required input):**
```bash
curl -L -o backend/models/centerbias_mit1003.npy \
  https://github.com/matthias-k/DeepGaze/releases/download/v1.0.0/centerbias_mit1003.npy
# fallback: np.zeros((1024,1024))
```
**IIE heatmap + score:**
```python
import numpy as np, torch, deepgaze_pytorch
from scipy.ndimage import zoom
from scipy.special import logsumexp
from PIL import Image

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
model = deepgaze_pytorch.DeepGazeIIE(pretrained=True).to(DEVICE).eval()

img = np.array(Image.open("ad.png").convert("RGB")); H, W = img.shape[:2]
cb = np.load("backend/models/centerbias_mit1003.npy")
cb = zoom(cb, (H/cb.shape[0], W/cb.shape[1]), order=0, mode='nearest'); cb -= logsumexp(cb)

image_tensor = torch.tensor(img.transpose(2,0,1)[None]).float().to(DEVICE)  # [1,3,H,W]
cb_tensor    = torch.tensor(cb[None]).float().to(DEVICE)                     # [1,H,W]
with torch.no_grad():
    log_density = model(image_tensor, cb_tensor)                            # [1,1,H,W]
density = np.exp(log_density[0,0].cpu().numpy())                            # sums to 1
heat = (density / density.max() * 255).astype(np.uint8)

def attention_score(density, box):           # box=(x0,y0,x1,y1)
    x0,y0,x1,y1 = box
    return float(density[y0:y1, x0:x1].sum())  # 0..1 share of attention
```
**III scanpath (numbered nodes):** same inputs + fixation history seeded at center; argmax each step, append, repeat ~8x → ordered `(x,y)` list. *(Stretch — IIE centroid is a fine proxy if cut.)*

### 2. Gemini image editing
Use **`gemini-2.5-flash-image`** (GA, ~1–2s, cheap, best-documented; "Nano Banana"). Newer if time: `gemini-3-pro-image` (Nano Banana Pro), `gemini-3.1-flash-image`.
```bash
pip install google-genai pillow   # set GEMINI_API_KEY in .env
```
```python
from google import genai
from PIL import Image
from io import BytesIO
client = genai.Client()
resp = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=["Make the product more eye-catching; mute the background.", Image.open("ad.png")])
for part in resp.candidates[0].content.parts:
    if part.inline_data:
        Image.open(BytesIO(part.inline_data.data)).save("ad_edited.png")
```

### 3. Stack
- **Backend:** FastAPI, one process: `/predict` `/edit` `/agents`. **Load DeepGaze models once at startup** (module-global), never per request. Run `uvicorn`.
- **Frontend:** React + Vite + **React Flow** — scanpath nodes AND the live agent pipeline as nodes that light up.
- **Libs:** FE `vite react reactflow axios tailwindcss`; BE `fastapi uvicorn[standard] python-multipart pillow numpy scipy torch deepgaze_pytorch google-genai langchain langchain-google-genai`.

### 4. Top risks + fallback
1. **DeepGaze install/download fails** → fall back to OpenCV saliency (`opencv-contrib-python`, `cv2.saliency.StaticSaliencySpectralResidual_create()`), keep `attention_score` identical so FE is unaffected.
2. **Gemini latency/quota in demo** → precompute edited images + scores for 2–3 hero ads, cache to disk, serve from cache; live "regenerate" as the risky-but-impressive option. 15s timeout + cached fallback.
3. **Score doesn't improve on stage** → cherry-pick hero ads where the lift is large/reliable; compute both scores server-side, present the directional delta; keep a backup ad with a big effect.

### 5. Folder structure
```
pixel/
├─ backend/  main.py · deepgaze_runner.py · gemini.py · agents.py · models/centerbias_mit1003.npy · requirements.txt
├─ frontend/ src/{App.tsx, components/HeatmapOverlay.tsx, ScanpathFlow.tsx, AgentFlow.tsx} · package.json
└─ samples/  hero ads + precomputed before/after (demo fallback)
```
**First-hour priorities:** (1) `deepgaze_runner.py` prints a real heatmap + score on a sample; (2) Vite + React Flow with a static scanpath. Wire Gemini + agents only once the before/after loop is proven.

**Sources:** [DeepGaze repo](https://github.com/matthias-k/DeepGaze) · [Gemini 2.5 Flash Image](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-image) · [Gemini image generation guide](https://ai.google.dev/gemini-api/docs/image-generation)
