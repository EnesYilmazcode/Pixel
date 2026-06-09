# Hackathon Context

> Multimodal hackathon. This file collects all context. Screenshots transcribed below; more raw context will be dumped further down and organized later.

---

## Official Judging Scorecard

Projects are scored on a **100-point scale**.

| # | Criterion | Points | What it measures |
|---|-----------|--------|------------------|
| 1 | **Problem Clarity** | 15 | Clear use case, clear target user, and a real or understandable problem. |
| 2 | **Execution** | 20 | Working demo, technically coherent build, and a complete enough flow to judge. |
| 3 | **Category Alignment** | 20 | Strong fit with the selected judging category and its core expectations. |
| 4 | **Sponsor Technology Integration** | 15 | Meaningful use of sponsor tools in the architecture, workflow, model behavior, retrieval layer, observability, or demo experience. Superficial mentions receive limited credit. |
| 5 | **User Experience** | 15 | Understandable interface, usable flow, clear feedback, and meaningful user control. |
| 6 | **Innovation & Originality** | 10 | Fresh, creative, surprising, or meaningfully different from standard AI demos. |
| 7 | **Presentation Quality** | 5 | Clear explanation, quick value demonstration, and strong use of demo time. |

**Total: 100 pts**

---

## Categories (Tracks)

You select one judging category (Category Alignment is worth 20 pts, so this choice matters).

### 1. Best Generative Media Tool
Focus on tools that facilitate the creation, editing, remixing, or analysis of diverse media formats via AI.

### 2. Best AI-Native Workflow
Solutions that exhibit complex planning and execution of multi-step processes beyond simple chat.

### 3. Best MultiModal Experience
Seamless integration of at least two disparate data modalities, such as text, voice, image, audio, video, documents, or structured data.

### 4. Best Multi-Agent Interface
Orchestration of collaborative AI agents working in tandem within a unified workspace.

---

## Event Overview

- **Name:** Multimodal Hacks: Build the Interface for Agents
- **Part of:** #NYTechWeek
- **Date:** Saturday, June 6, 2026 · 9:00 AM – 6:00 PM
- **Venue:** Betaworks Studios — 29 Little W 12th St, New York, NY
- **Capacity:** 120 spots (RSVPs closed)
- **Core theme:** *The interface layer for AI agents is expanding far beyond the command line.* Build voice-first agents, multimodal copilots, creative tools, workflow assistants, or new ways for people to interact with AI — **ambitious, useful, and demo-ready in a single day.**

### Rules
- **Teams of up to 3 people.**
- **All projects must be started from scratch on the day of the hackathon** (to keep it fair and fresh).
- **Up to 5 submission categories → 5 winning teams.**
  - ⚠️ Only **4** categories appear in the screenshots (see Categories above). There may be a **5th category** we don't have yet — worth confirming.

## Sponsors & Their Tech

These are the sponsor tools that count toward **Sponsor Technology Integration (15 pts)** — remember, superficial mentions get limited credit, so integrate them meaningfully.

| Sponsor | What it is | Natural use in a build |
|---------|-----------|------------------------|
| **Google DeepMind** | Frontier AI research lab — Gemini models, generative media | Core LLM / multimodal model, image/video/audio gen |
| **Pinecone** | Managed vector database | Long-term memory, RAG, search, recommendations |
| **LangChain** | Open-source agent framework | Orchestrating models, tools, and data; multi-step agents |
| **Cursor** | AI-native code editor / coding agent | Dev tooling (more a build aid than a runtime dependency) |
| **Clerk** | Auth & user management | Drop-in sign-in, orgs, billing-aware user flows |
| **Sendblue** | Messaging platform | Spin up **iMessage-capable phone numbers** for agents |
| **Forever 22** | Co-host / sponsor (Betaworks) | — |
| **Betaworks** | Host / studio | Venue & organizer |

## People

- **MC:** Mari Zumbro — COO, Filament (multiplayer platform for professionals + agents)
- **Judges:**
  - Marc — Danger Testing
  - Tommy — ClawCon
  - Yiliu — Collaborator AI
  - Kaya Jones — Forever22 / Betaworks
- **AMA Speaker:** Vince Trost — CEO, Plastic Labs

## Run of Show (Sat, June 6)

| Time | Item |
|------|------|
| 9:00 – 9:15 AM | Doors open (check-in, coffee, bagels; sponsor booths + popups) |
| 9:15 – 10:15 AM | Introductions and sponsor presentations |
| 10:15 – 10:30 AM | **Challenge Reveal** |
| 10:30 AM | **Building begins** |
| 12:00 PM | Lunch served |
| 12:30 – 1:00 PM | AMA with Plastic Labs CEO Vince Trost |
| 3:00 – 5:00 PM | **Demos** |
| 5:00 – 6:00 PM | Winners announced & doors close |

> Effective build window: **~10:30 AM → 3:00 PM (≈4.5 hrs)** before demos start.

## Project Direction (CHOSEN)

**Working name:** Pixel (gaze-driven ad/campaign optimizer)

**One-liner:** Upload existing campaign creative → AI predicts where human eyes will look → agents iteratively edit the image to direct attention where the brand wants it → prove it with an objective before/after attention score.

### Core loop
1. **Ingest** — user uploads a campaign image (+ optional goal: "drive attention to logo / CTA").
2. **Analyze** — DeepGaze predicts visual attention (heatmap + scanpath).
3. **Visualize** — overlay heatmap + numbered gaze-path nodes on the image.
4. **Optimize** — agents propose edits and call Gemini image editing ("Nano Banana") to move/resize/recolor elements.
5. **Re-score** — re-run DeepGaze, show the attention metric improved.
6. **Branch** — spin up multiple agent variants, compare, pick winner. *(stretch)*

### Target track
Primary: **Best Multi-Agent Interface** (agents optimizing branches in a unified node canvas — dead-on for "interface for agents").
Backup framing available for **Best AI-Native Workflow** and **Best MultiModal Experience**.

### Why it scores well
- **Measurable** before/after attention number → Problem Clarity (15) + Execution (20) + Presentation (5).
- **Novel** saliency-guided iterative editing loop → Innovation (10).
- **Sponsor-dense** architecture → Sponsor Integration (15).

---

## DeepGaze Research & Decision

The official models live at **github.com/matthias-k/DeepGaze** (PyTorch, pretrained weights for DeepGaze I, II, IIE, III, MSDB).

| Concern | Finding |
|---|---|
| **Heatmap mode** | **DeepGaze IIE** — spatial saliency / fixation-density map. SOTA, *calibrated*, robust, single forward pass. Outputs a log-density map of where people look overall (no ordering). |
| **Node / scanpath mode** | **DeepGaze III** — predicts the *sequence* of fixations conditioned on gaze history. Reproduces real saccade amplitude/direction stats. Best for narrative/flow. |
| **III's weakness** | Less predictive on scenes with multiple small salient objects / long saccades — i.e. busy ad creative. So don't use it as the sole optimization signal. |
| **Centerbias** | **Both models require a `centerbias` log-density input.** Use the provided MIT1003 centerbias file, or a uniform centerbias as fallback. |
| **Deps** | PyTorch, NumPy, SciPy. (MSDB also needs CLIP + DINOv2 — not needed for us.) |
| **Inference (IIE)** | `model = deepgaze_pytorch.DeepGazeIIE(pretrained=True).to(DEVICE)`<br>`log_density = model(image_tensor, centerbias_tensor)` |

**Decision:** Use **BOTH**.
- **DeepGaze IIE (heatmap) = optimization objective** (the score agents optimize against: a size-invariant attention-on-target *prominence index* — 50 = average salience for the region's size, not a raw % — plus attention spread/entropy).
- **DeepGaze III (scanpath) = hero visualization** (numbered gaze-path nodes + arrows overlaid on image).

**Sources:**
- [DeepGaze III — JOV (Kümmerer et al.)](https://jov.arvojournals.org/article.aspx?articleid=2778776)
- [DeepGaze III — PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC9055565/)
- [DeepGaze IIE — Calibrated SOTA saliency](https://www.researchgate.net/publication/358922466_DeepGaze_IIE_Calibrated_prediction_in_and_out-of-domain_for_state-of-the-art_saliency_modeling)
- [Official DeepGaze repo (matthias-k/DeepGaze)](https://github.com/matthias-k/DeepGaze)

---

## Proposed Sponsor Architecture

| Sponsor | Where it lives in Pixel |
|---|---|
| **Google DeepMind / Gemini** | Image editing (Nano Banana) + reasoning about *what* to move and why |
| **LangChain** | Orchestrates the analyze → propose → edit → re-score → branch agent loop |
| **Pinecone** | Memory: store winning ad patterns / brand guidelines; RAG to ground edit suggestions |
| **Clerk** | Auth + brand/team workspaces |
| **Sendblue** | (stretch) send variants to a stakeholder for approval over iMessage |
| **Cursor** | Build-time coding agent (not a runtime dependency) |

---

## Build Plan & Task Split (2 people + cloud agents)

> **Working agreement:** private repo, **commit + push frequently** so both cloud agents share fresh context. **No API keys in git** — wire secrets via `.env` / env vars **last**. Planning/docs first.

**Milestone 0 — Skeleton (do first, together):** repo scaffold, `.gitignore` (include `.env`), README, choose stack (likely Python backend for DeepGaze + web frontend for canvas).

**Track A — Vision/Scoring (the "truth" engine):**
1. Get DeepGaze IIE running on a sample image → heatmap.
2. Get DeepGaze III → scanpath nodes.
3. Define the **attention metric** (attention-on-target %, spread/entropy) → the before/after number.

**Track B — Agent loop + editing:**
1. Gemini image-edit call wrapper.
2. LangChain orchestration: propose edit → apply → re-score → keep if improved.
3. Branching/variants (stretch).

**Track C — Interface (demo-maker):**
1. Upload + canvas view.
2. Heatmap overlay + numbered gaze-path nodes.
3. Before/after score display (the money shot).

**De-risk first:** get **one** image → heatmap → one edit → re-score showing the number go up. That single loop is already a winning demo; everything else is stretch.

---

## Session Research Log — June 6 (open product questions)

> Captured live during build planning. These are **proposals/decisions for discussion**, not yet locked. Flag in standup before acting.

### 1. LangSmith — observability + eval for the agent loop
LangSmith (LangChain's tracing/eval platform) fits Pixel cheaply because our whole pitch is *an iterative agent loop with an objective score*.

| Use | Effort | Payoff |
|---|---|---|
| **Trace the optimize loop** | ~5 min (3 env vars: `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`) | Every iteration is a nested trace (score in → Gemini edit → score out). Debug *which* step regressed instead of print-statements. |
| **Log `attention_score` as run feedback** | small | Free chart of attention-per-iteration → an objective **rising-score curve** as a judge artifact (stronger than one before/after pair). `client.create_feedback(run_id, key="attention_score", score=...)`. |
| **Dataset eval over 5–10 sample ads** *(stretch)* | medium (needs sample data) | Turns "worked on one image" into "improved attention on N/10" — quantitative proof. |

**Why it earns points:** makes the **LangChain** integration *load-bearing, not name-dropped* — we observe + evaluate the loop, not just call it. Doubles as the demo dashboard.
**Recommendation:** do tracing + score-logging (nearly free, big debug + demo value); dataset eval only if core loop is solid.

### 2. Input mode — upload real ad vs. text→research→generate
Question raised: instead of uploading a pre-existing ad, type text → an agent does market research on the company → generate an ad from scratch → then optimize.

**Decision: keep BOTH as two demo modes; do not replace upload.**

| Mode | Flow | Role |
|---|---|---|
| **A — the proof** (de-risked core) | Upload a **real brand ad** → optimize → show the honest before/after (the size-invariant prominence index; the optimizer keeps the best variant and reports the real delta, even when flat/negative) | Credibility. Baseline is a real agency-shipped ad, so a real lift is unimpeachable — and an honest non-lift is still credible. |
| **B — the wow** (optional front door) | Type company name → research agent (+ Pinecone RAG) → generate ad → hand off to the **same** gaze loop | Hook + richer multi-agent story (research → brief → generate → optimize). **Pre-cache ≥1 company** so a live failure can't sink the demo. |

**Key risk with text-in:** if the agent generates the "before," we're optimizing our own strawman — a judge can ask "did attention rise because the editor is good, or because v1 was deliberately weak?" Uploading a real ad removes that doubt. The score lift is *objectively real* either way (DeepGaze is source-agnostic), but the real-ad baseline is more persuasive.
**Note:** "from scratch on the day" = our **code**, not the ad. Uploading a real brand ad as demo *input* is fine (it's data).
**RESOLVED (hybrid):** ship both entry points → same gaze loop. Mode B generates a **rough v1**, then **visibly optimizes it** — generation is the wow, the v1→optimized delta stays the money shot. Keep ≥1 real-ad example (Mode A) for credibility; pre-cache the Mode-B path for the live demo. *(see PLAN.md Decisions Log)*

---

## Additional Context (raw dump — to be organized later)

<!-- Paste more context below this line. -->


