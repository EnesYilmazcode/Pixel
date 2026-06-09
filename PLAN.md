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

## Work Split & Ownership (2 people) — spine-first, then vertical fork

**Don't split by tier (frontend vs backend).** That's the trap — the FE person mocks for hours and integration happens late and painfully. We DO have two runtimes (Python for DeepGaze — no JS port; React for the node canvas), but that's a *technical* boundary, not how we assign people.

**Phase 1 — Build the spine TOGETHER (now → ~1:00). One vertical, integrated early.**
The only thing that must work: **upload real ad → DeepGaze heatmap + score → one Gemini edit → re-score → show the real before/after** (the score is a size-invariant prominence index, and the delta is whatever actually happened — we keep the best variant and report it honestly, including a flat/negative result), with a dead-simple UI (image + heatmap overlay + the score).
- One person drives the **Python** side (DeepGaze runner + `/predict` + `/edit`, with the dimension-fix from the Critical Risk section baked in).
- Other drives the **React shell** (upload, show image, fetch + render heatmap, show score) AND wires it to the real endpoints *as they come up* — tight loop, integrate continuously, not at a checkpoint.
- Goal: by ~1:00 the money shot works end-to-end on ONE hero ad. Pair on it; this is the demo.

**Phase 2 — Fork into two verticals (~1:00 → 2:15). Each owns a full slice, separate files.**
- **Vertical 1 — Polish & proof:** demo hero visuals (heatmap wipe slider, animated score counter, distractor callout), dimension-fix hardening, hero-ad precache, the upload Mode-A path. Owns `App` shell + `components/Heatmap*`.
- **Vertical 2 — Agent layer & wow:** LangChain leader + Pinecone competitive analysis (`/agents`), the React Flow **agent-pipeline canvas**, LangSmith score chart, voice (Web Speech), Mode-B generate front door. Owns `components/AgentFlow*` + `backend/agents.py`.
- Cloud agents take sub-tasks *within* a vertical (e.g. seed Pinecone, write the precache script).

**🔑 Anti-collision rules (matter most in Phase 2):**
- Agree the `/agents` + `/predict` + `/edit` JSON shapes during Phase 1; freeze them.
- Each vertical owns **separate files/folders** — don't both edit `App.tsx`; compose via components.
- Commit + push small and often; **pull/rebase before push** (see CLAUDE.md). Two cloud agents are live in this repo.

---

## Architecture Spec

**Goal:** Upload ad image → predict where eyes look (DeepGaze) → agents edit image (Gemini "Nano Banana") to pull attention toward the brand target (logo/CTA) → prove it with a before/after attention score.

### Agent fleet (LOCKED — don't invent new agents mid-build)

**6 agents, with memorable display names for the canvas.** Backend tool names (in parens) stay stable so the API contract doesn't churn. Build the 5 MVP agents first; **Judge** is stretch (turns on only with branching).

| # | Canvas name | Role | Single Responsibility | Inputs | Outputs | Model/Tool | Tier |
|---|---|---|---|---|---|---|---|
| 1 | **Director** | Leader / Orchestrator | Run the loop; fuse gaze leaks + tactics + brand rules into ONE `edit_directive`; decide loop/stop. | `image`, `brand`, `target` | `winning_variant`, score history, rationale | Gemini (AgentExecutor) | MVP |
| 2 | **Insider** | Brand Understanding (*"our own"*) | Brief on **our** brand: product, audience, tone, palette, target to amplify, do's/don'ts. | `brand`, optional assets | `BrandBrief` | Gemini (`analyze_brand`) | MVP |
| 3 | **Scout** | Competitive Analysis (*"dark horse"*) | What **competitors** + our past ads do well/poorly → 3–5 "winning patterns." | `brand`, `BrandBrief` | `CompetitiveInsights` | Pinecone RAG → Gemini (`competitive_insights`) | MVP |
| 4 | **Eye** | Gaze Analysis | DeepGaze IIE + III; compute attention-on-target + distractors. | `image`, `target_region` | `GazeReport` (heatmap, scanpath, score, distractors) | DeepGaze (`score_gaze`) | MVP |
| 5 | **Retoucher** | Creative Editor | Turn `edit_directive` into ONE Gemini edit, apply, hand back for re-score. | `image`, briefs, `GazeReport`, `edit_directive` | `variant_image`, `edit_description` | Gemini image (`edit_image`) | MVP |
| 6 | **Judge** | Critic (*NEW*) | Score/compare branch variants, enforce brand do's/don'ts, pick the winner. | `variants[]`, `BrandBrief`, scores | `winner`, per-variant verdict + reason | Gemini (`judge_variants`) | **Stretch** (with branching) |

**Why these six:** **Insider** (us) + **Scout** (them) are the two research agents the team wanted; **Eye** is the objective truth; **Director** turns analysis into action; **Retoucher** executes; **Judge** closes the branching loop. No two agents share a responsibility — each is one mockable tool.

### Canvas choreography (this is what wins *Best Multi-Agent **Interface***)
Agents are **React Flow nodes that light up as they run** — the pipeline IS the interface, not a hidden backend.
- **Fan-out (parallel):** **Insider** + **Scout** + **Eye (baseline)** fire at once → three nodes pulse simultaneously. Visible parallelism reads as "a team," not a script.
- **Converge:** edges flow into **Director**, which emits its one-line `edit_directive` as node text — *reasoning made visible*.
- **Act:** **Retoucher** runs → new image + the **real before/after score** animate in (the money shot). The optimizer keeps the best variant it finds and reports the honest delta — failed branches stay visible rather than being hidden behind an always-climbing number.
- **Loop:** Director→Retoucher→Eye loops up to `MAX=3`; each pass adds a node so the graph visibly grows.
- **Branch + Judge (stretch):** Director fans 2–3 **Retoucher** variants → **Judge** compares → winning edge highlights.
- **Node states:** grey → pulsing → green, so a judge *sees* the fleet working without reading logs.

### Orchestration flow (Director's sequence)
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
- One `AgentExecutor` as **Director** (a.k.a. Leader); sub-agents exposed as **Tools** (not nested agents). Loop is a plain Python `for`. **No LangGraph** — fixed sequence doesn't need it.
- Tools: `analyze_brand(brand)`, `competitive_insights(brand, brief)`, `score_gaze(image_path, target_region)`, `edit_image(image_path, directive)`, `judge_variants(variants, brief)` *(stretch)*.
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
`target_attention_score` ∈ [0,1] is a **size-invariant prominence index** (NOT a raw fraction): `ratio = (fixation mass inside target_region) / (region's area fraction)`, then `score = ratio/(ratio+1)`, so **0.5 = average salience for the region's size**, >0.5 = it out-pulls its size. This is the honest headline — raw mass-in-box would reward simply enlarging the target. The raw mass is still kept as `target_salience` (used by the reward-hack guard to catch "win by suppression"). **The single number every agent optimizes and the demo headlines.**

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

---

## ⚠️ CRITICAL BUILD RISK — read before coding the optimize loop

**Gemini image editing does NOT preserve input dimensions, and has no mask/inpainting.** This can silently invalidate the entire before/after comparison (our money shot). Confirmed via official docs + Google's own acknowledgment (June 2026).

**What breaks:**
1. **Output resolution is not your input's.** Output is capped to a ~1,048,576-px budget (1024×1024-equiv) and snaps to ~10 aspect buckets. A backend update made it frequently default to **1:1 / 1024×1024 even for non-square inputs** (real case: 2048×1024 in → 1472×704 out). If you score a **fixed pixel bounding box** on raw before/after images, the box doesn't line up → comparison is invalid.
2. **No binary-mask inpainting in the Gemini API** — editing is *semantic* (prompt-described regions only). Pixel-mask inpainting is Imagen-only (and Imagen is being shut down 2026-06-24). So expect possible **identity/layout drift**: the logo/CTA can move or change, so the original target box may no longer contain the target after the edit.

**Required handling (build this into `deepgaze_runner.py` + `gemini.py` from the start):**
1. **Record input `(W,H)`; resample every edited output back to exactly `(W,H)`** (`PIL .resize((W,H), LANCZOS)`) before scoring. If aspect ratio changed, **letterbox/pad to input AR then resize** (don't stretch — distortion perturbs saliency). Log raw output dims to detect AR changes.
2. **Never hard-code a pixel box — use normalized coords** `[x/W, y/H, w/W, h/H]` so the target survives resizing. The headline score is the size-invariant *prominence* (mass-in-box ÷ box area fraction, squashed to 0–1), not raw mass — both resolution- and size-invariant, so it can't be won by enlarging the target.
3. **Re-detect the target after each edit** (Gemini/vision call returning a bbox, or template match) rather than trusting the original box — guards against drift. Report BOTH the original-box score and the re-detected-box score; agreement = trustworthy, divergence = flag.
4. **Integrity gate:** reject/redo an edit if output AR differs from input beyond tolerance, or if the target detector can't relocate the logo/CTA (means the edit garbled it). Stops a degenerate edit faking a "win."
5. **Prompt for localized edits** (Google's official template): *"Using the provided image, change only the [element] to [X]. Keep everything else exactly the same — preserve composition, framing, lighting, and the position/size of the logo and CTA. Do not change the aspect ratio or crop."* One focused change per call.
6. **Pin the model id** `gemini-2.5-flash-image` (GA; EOL 2026-10-02). Verify output dims empirically with ONE test call before trusting any assumption.

**Sources:** [aspect-ratio regression thread (Google ack)](https://discuss.ai.google.dev/t/gemini-2-5-flash-nano-banana-auto-aspect-ratio-issue-output-image-has-different-aspect-ratio/108225) · [official prompt guide (localized-edit template)](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/) · [GA + aspect ratios](https://developers.googleblog.com/en/gemini-2-5-flash-image-now-ready-for-production-with-new-aspect-ratios/) · [mask inpainting is Imagen-only](https://firebase.google.com/docs/ai-logic/edit-images-imagen-overview)

### Drop-in helper (structure-agnostic — paste into the scoring path / `Retoucher` + `Eye`)
```python
from PIL import Image, ImageOps
import numpy as np

def align_to_input(edited: Image.Image, in_w: int, in_h: int) -> Image.Image:
    """Make the edited image EXACTLY the input's WxH so before/after are comparable.
    Pad-to-aspect (no stretch) then resize, so geometry isn't distorted — distortion
    would itself change saliency."""
    if edited.size == (in_w, in_h):
        return edited
    return ImageOps.pad(edited, (in_w, in_h), method=Image.LANCZOS, color=(0, 0, 0))

def attention_in_box(density: np.ndarray, nbox) -> float:
    """density: DeepGaze prob map. nbox: NORMALIZED (x,y,w,h) in [0,1].
    Returns fraction of total attention mass inside the box (resolution-invariant)."""
    H, W = density.shape
    x, y, bw, bh = nbox
    x0, y0 = int(x * W), int(y * H)
    x1, y1 = int((x + bw) * W), int((y + bh) * H)
    d = density / density.sum()                      # re-normalize after any resize
    return float(d[y0:y1, x0:x1].sum())

def integrity_ok(in_w, in_h, raw_out_w, raw_out_h, target_relocated, ar_tol=0.06):
    """Reject a degenerate edit before trusting its score."""
    in_ar, out_ar = in_w / in_h, raw_out_w / raw_out_h
    if abs(in_ar - out_ar) / in_ar > ar_tol:
        return False                                 # aspect changed too much
    return target_relocated                          # detector must re-find logo/CTA

# Flow per edit (Retoucher -> Eye):
#   in_w, in_h = original.size
#   raw = gemini_edit(original, "change only ...; keep everything else identical; don't crop")
#   if not integrity_ok(in_w, in_h, *raw.size, detect_target(raw)): redo / keep best
#   aligned = align_to_input(raw, in_w, in_h)
#   nbox = detect_target_nbox(aligned)               # RE-DETECT, don't reuse the old box
#   score_after = attention_in_box(deepgaze(aligned), nbox)
```
`detect_target_nbox` = a Gemini vision call returning a normalized bbox, or a template match. Report both the original-box and re-detected-box scores; agreement = trustworthy delta.

---

## Voice / Multimodal Input — DECISION

The event theme is voice-first / "beyond the command line," so a voice interaction is worth points. But full **Gemini Live API** (WebSocket duplex audio) is a **~2-hour rabbit hole** (PCM resampling, AudioWorklet, mic perms need HTTPS/localhost, echo/barge-in, plus wiring it to drive the agent loop) — too risky with the core loop unproven.

**Decision: use the Web Speech API wrapper, NOT full Gemini Live.**
- Browser `SpeechRecognition` (STT) → feed the transcript into the **existing** agent pipeline → `speechSynthesis` (TTS) reads the answer back. ~45 min, zero new infra, **cannot break the core loop** because it just wraps it. Demo on Chrome/Edge (STT support). Chunk TTS >~250 chars.
- Pitch to judges: *"You talk to Pixel; it sees the ad, reasons over it, and talks back."* Name-drop **Gemini Live native audio** (`gemini-live-2.5-flash-native-audio`, 30 HD voices) as the production roadmap.
- **Timebox 45 min; hard stop ~2:15.** If not solid, demo silent with the spoken script as on-screen text. Only attempt full Gemini Live if the core loop finishes with real time to spare — and keep Web Speech as the fallback.
- If we want a stronger Gemini story without audio risk: lean on **Gemini multimodal text** ("the agent literally sees the ad" — image+text reasoning), which we already use.

**Sources:** [Gemini Live API overview](https://ai.google.dev/gemini-api/docs/live-api) · [live-api-web-console (React starter)](https://github.com/google-gemini/live-api-web-console) · [Web Speech API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API) · [STT support (caniuse)](https://caniuse.com/speech-recognition)

---

## Demo & Visuals (what looks cool + earns UX/Presentation points)

The demo IS the product for judging (Execution 20 + UX 15 + Presentation 5 + Innovation 10). Build the UI around these beats:

**Hero visuals (in priority order):**
1. **Before/after heatmap wipe** — a draggable slider that wipes between the original and optimized heatmap overlay on the same ad. Instantly legible, very screenshot-able.
2. **Rising attention-score counter** — big animated number, `12% → 41%`, with the delta highlighted. The single most persuasive object on screen.
3. **Live agent pipeline (React Flow)** — nodes Brand → Competitor → Gaze → Editor light up in sequence as the leader runs, score updating on the Gaze node each iteration. This visually *proves* the "multi-agent" claim (Best Multi-Agent Interface track).
4. **Attention-per-iteration line chart** — the rising curve over iterations (free from LangSmith feedback, or plot locally). Turns one before/after into an objective trend → strong judge artifact.
5. **Distractor callout** — red box on the attention thief ("model's face — 38% of attention") with the fix annotated. Makes the problem visceral.
6. **Scanpath nodes** — numbered fixation dots 1→2→3 animating across the ad (DeepGaze III). The "eye-tracking" wow; stretch.

**Demo narrative (90 sec):** upload real Coca-Cola ad → heatmap shows attention wasted on the face, only 12% on the can → hit Optimize → agent pipeline lights up ("it checked what Pepsi does well") → optimized image + re-score: **can attention 12% → 41%** → (stretch) "Approve?" via voice/Sendblue.

**UX must-haves for points:** clear loading states on each agent node (not a frozen spinner), the user can pick/adjust the target region, edits are explained in plain language ("boosted CTA contrast, dimmed upper-right"), and nothing blocks on a live model call without a cached fallback.

---

## Decisions Log (running)
- **Input mode → HYBRID (locked):** ship BOTH entry points converging on the same gaze loop. Mode B = type company → research agent → **generate a rough v1** → then **visibly optimize it** (so generation is the wow AND the v1→optimized delta is the money shot). Keep ≥1 **real-ad** example (Mode A) for the unimpeachable proof, and **pre-cache** the Mode-B generated path so live latency/flakiness can't sink the demo. Not technically hard (two entry points, one loop); the cost is demo risk, handled by caching.
- **Team workflow → spine-first, then vertical fork** (NOT a frontend/backend tier split — see Work Split above).
- **LangSmith:** adopt tracing + `attention_score` feedback logging (nearly free; debug + demo chart); dataset eval is stretch. *(detail in HACKATHON_CONTEXT Session Research Log)*
- **Voice:** Web Speech API wrapper, not full Gemini Live (see above).
- **Gemini edit:** must resample-to-input-dims + normalized box + re-detect target + integrity gate (see Critical Build Risk above).
- **Sponsors committed:** Gemini, LangChain (+LangSmith), Pinecone, Clerk. Stretch: Web Speech voice (Gemini Live as roadmap), Sendblue.
