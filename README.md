# Pixel

Pixel predicts where people look in an ad, then uses AI agents to redesign it so attention lands on the brand. It re-scores every edit with a before and after attention metric, so the change is measured rather than guessed.

Built in one day for Multimodal Hacks: Build the Interface for Agents (#NYTechWeek, June 6 2026). Track: Best Multi-Agent Interface.

---

## The problem
Brands spend millions on creative but can't see where attention goes until after launch. Pixel shows where attention lands and suggests fixes before any money goes to media.

## How it works
1. **Pick a campaign.** Choose a sample ad or upload your own.
2. **Analyze.** DeepGaze predicts visual attention and returns a saliency heatmap, an attention-on-target score, the regions stealing attention, and the predicted gaze path. The score is a size-invariant prominence index. 50 means average salience for the region's size, and higher means it out-pulls its size. It is not a raw percentage of attention.
3. **Optimize.** The agents grow the campaign one branch at a time. Each branch is a real Nano Banana edit such as de-clutter, reframe, strengthen the logo, or add a headline. DeepGaze re-scores it, a brand-fit Judge gates it, and a reward-hack guard checks it. The optimizer keeps the best variant and reports the real before and after. An edit that scores worse or fails to beat the original stays visible instead of being hidden. Edits that win by suppressing the rest of the frame, or by a change too small to see, are rejected. You watch each branch land and choose whether to spawn another.
4. **Prove it.** The before and after score updates live with the real delta, including when it is flat or negative. You can download the finished creative.

## The agent fleet
A **Director** orchestrates five specialists, composed as a LangChain pipeline. This is the interface for agents.

| Agent | Role |
|---|---|
| **Director** | Orchestrates the pipeline, composes the edit strategy, and keeps the best result. |
| **Insider** | Builds the brand brief (audience, tone, palette, do's and don'ts) via Gemini. |
| **Scout** | Pulls competitor ad tactics from a Pinecone knowledge base (RAG). |
| **Eye** | Runs DeepGaze for the attention heatmap, attention-on-target score, distractors, and gaze path. |
| **Retoucher** | Applies the edit with Gemini "Nano Banana" image generation. |
| **Judge** | Gemini brand-fit gate. It vetoes off-brand or garish edits so attention can't be won cheaply. A reward-hack guard also rejects suppression and invisible cheats. |

## How we used each technology

**DeepGaze IIE (Google/Tübingen, PyTorch)** — our objective gaze model and the metric the whole system optimizes. We load the pretrained IIE ensemble once, feed it the image plus a *flat* (content-driven) centerbias, and turn its output into a normalized attention map. The **attention-on-target score** is a **size-invariant prominence index** — attention mass in the brand's region divided by that region's area fraction, squashed to 0–1 (50 = average salience for its size). It's deliberately *not* a raw percentage, so the optimizer can't win by simply enlarging the target. That index is the number we show before and after, and the fitness the optimizer climbs; `/health` reports whether the real model or the CPU fallback produced it, driving a LIVE/DEMO badge.

**Google Gemini (Nano Banana)** — `gemini-2.5-flash-image` does the actual creative edits; Gemini's vision/text models also write the brand brief, name the attention thieves, detect the brand target, and act as the Judge that scores brand-fit.

**Pinecone** — a vector knowledge base of competitor ad analyses (embedded with `gemini-embedding-001`). The Scout agent retrieves the most relevant rival tactics for the brand via similarity search and feeds them into the edit strategy.

**LangChain** — orchestrates the Director's multi-agent pipeline as an LCEL chain, with LangSmith tracing instrumented for observability.

**Clerk** — authentication: sign-in and user profile in the app.

## Features
- **Sample gallery + upload** — analyze a real brand ad in one click, or bring your own.
- **Attention analysis** — heatmap overlay, the size-invariant attention-on-target prominence index, named "attention thieves," and the gaze path.
- **Interactive branch optimizer** — grow the optimization one real edit at a time; watch the branch tree build, click any branch to see the exact Nano Banana prompt and its score.
- **Optional suggestion box** — type your own instruction and the Retoucher folds it into the edit.
- **Before/after attention score** — the objective, honest proof: the real delta (including when an edit didn't help), with a reward-hack guard rejecting suppression/invisible cheats.
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
