# Pixel — Agentic Campaign Optimization

> **See where your audience looks. Let a team of agents fix it. Prove the lift.**

Pixel takes a brand's ad creative, predicts where human eyes actually land using a trained gaze model, then runs a fleet of AI agents — informed by live competitor analysis — that redesign the image so attention flows to the brand (logo / product / CTA). Every edit is re-scored with an **objective before/after attention metric**, so the improvement is measured, not guessed.

Built in one day for **Multimodal Hacks: Build the Interface for Agents** (#NYTechWeek, June 6 2026).
**Primary track:** Best Multi-Agent Interface.

---

## The problem
Brands spend millions on creative but can't see where attention actually goes until after launch. Pixel makes attention **visible and actionable** — before a dollar is spent on media.

## How it works
1. **Pick a campaign** — choose a sample ad or upload your own.
2. **Analyze** — DeepGaze predicts visual attention: a saliency **heatmap**, the **attention-on-target score** (% of attention landing on the brand), the **attention thieves** stealing it, and the predicted **gaze path**.
3. **Optimize** — the agent fleet grows the campaign one branch at a time: each branch is a real Nano Banana edit (de-clutter, reframe, strengthen the logo, add a headline…), re-scored by DeepGaze and gated by a brand-fit Judge. You watch each branch land and choose whether to spawn another.
4. **Prove it** — the **before → after attention score** updates live, and you can **download** the finalized creative.

## The agent fleet
A **Director** orchestrates five specialists (composed as a LangChain pipeline) — this is the "interface for agents":

| Agent | Role |
|---|---|
| **Director** | Orchestrates the pipeline, composes the edit strategy, and keeps the best result. |
| **Insider** | Builds the brand brief (audience, tone, palette, do's/don'ts) via Gemini. |
| **Scout** | Pulls real competitor ad tactics from a Pinecone knowledge base (RAG). |
| **Eye** | Runs DeepGaze — attention heatmap, attention-on-target score, distractors, gaze path. |
| **Retoucher** | Applies the edit with Gemini "Nano Banana" image generation. |
| **Judge** | Gemini brand-fit/quality gate — vetoes off-brand or garish edits so attention can't be won cheaply. |

## How we used each technology

**DeepGaze IIE (Google/Tübingen, PyTorch)** — our objective gaze model and the metric the whole system optimizes. We load the pretrained IIE ensemble once on the GPU, feed it the image plus a centerbias prior, and turn its output into a normalized attention map. The **attention-on-target score** is the fraction of that map landing in the brand's region — the number we show before and after, and the fitness the optimizer climbs.

**Google Gemini (Nano Banana)** — `gemini-2.5-flash-image` does the actual creative edits; Gemini's vision/text models also write the brand brief, name the attention thieves, detect the brand target, and act as the Judge that scores brand-fit.

**Pinecone** — a vector knowledge base of competitor ad analyses (embedded with `gemini-embedding-001`). The Scout agent retrieves the most relevant rival tactics for the brand via similarity search and feeds them into the edit strategy.

**LangChain** — orchestrates the Director's multi-agent pipeline as an LCEL chain, with LangSmith tracing instrumented for observability.

**Clerk** — authentication: sign-in and user profile in the app.

## Features
- **Sample gallery + upload** — analyze a real brand ad in one click, or bring your own.
- **Attention analysis** — heatmap overlay, attention-on-target %, named "attention thieves," and the gaze path.
- **Interactive branch optimizer** — grow the optimization one real edit at a time; watch the branch tree build, click any branch to see the exact Nano Banana prompt and its score.
- **Optional suggestion box** — type your own instruction and the Retoucher folds it into the edit.
- **Before/after attention score** — the objective proof of the lift.
- **Download** the finalized optimized creative.
- **Live activity log** — see each agent run (DeepGaze, Scout, Retoucher, Judge…) as it happens.
- **Campaign save/resume** — persist a campaign and its runs.

## Tech stack
- **Backend:** Python + FastAPI — `/predict`, `/edit`, `/agents`, `/optimize/step`, `/campaigns`, `/health`.
- **Frontend:** Vite + React + TypeScript, custom components (light "optical instrument" theme).
- **Models:** DeepGaze IIE (PyTorch, GPU) · Gemini 2.5 Flash Image + Gemini text.
- **Memory / orchestration / auth:** Pinecone · LangChain (+ LangSmith) · Clerk.

## Repo layout
```
pixel/
├─ backend/    FastAPI · deepgaze_runner.py · gemini.py · agents.py · branch.py
│              competitive.py · pinecone_seed.py · storage.py · main.py
├─ frontend/   Vite + React + TS · App.tsx · BranchWorkspace.tsx · ActivityLog.tsx · …
└─ README.md
```

## Run it
**Backend**
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate     # Windows (or: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
**Frontend**
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```
**Keys** (git-ignored): `backend/.env` → `GEMINI_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX`; `frontend/.env.local` → `VITE_CLERK_PUBLISHABLE_KEY`. Seed the competitor knowledge base once with `python backend/pinecone_seed.py`.
