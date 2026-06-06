# CLAUDE.md — Pixel (Multimodal Hacks, NYC · June 6 2026)

> Read this first, every session. Full event/scoring/strategy detail lives in **`HACKATHON_CONTEXT.md`** — open it before making product decisions.

## What we're building
**Pixel** — a gaze-driven ad/campaign optimizer. Upload campaign creative → AI predicts where human eyes look (DeepGaze) → agents iteratively edit the image (Gemini "Nano Banana") to direct attention to the brand's target (logo / CTA) → prove it with an **objective before/after attention score**.

- **Primary track:** Best Multi-Agent Interface (backup: AI-Native Workflow / MultiModal Experience).
- **The money shot:** a single image → heatmap → one edit → re-score showing the attention number go UP. Land that first; everything else is stretch.

## ⏱️ This is a one-day hackathon — optimize for a working demo, not perfection
- Build window is ~10:30 AM → 3:00 PM demos. Scope ruthlessly. De-risk the core loop before polishing.
- Rule: **all code started from scratch on the day.** Don't pull in pre-built project code.

## 🔁 Working agreement (CRITICAL — two cloud agents share this repo)
1. **Commit AND push frequently.** After every meaningful unit of work (a function, a fixed bug, a doc update). Small, frequent commits keep both agents' context fresh and avoid conflicts. Don't sit on uncommitted work.
2. **Pull before you start and before you push.** Two agents are writing to `main` — rebase/merge early and often to avoid divergence.
3. **NEVER commit secrets.** No API keys, tokens, or `.env` files in git — `.gitignore` already blocks them. Wire secrets via env vars, and do that **last**. Plan and stub now; add real keys at the end.
4. **Write clear commit messages** — the *other* agent reads them to understand what changed. State what and why.
5. **Update `HACKATHON_CONTEXT.md`** when a decision changes, so the plan stays the source of truth.
6. **Leave the tree runnable.** Don't push half-edits that break `import`/build for the other agent.

## Sponsor tech to integrate (worth 15 pts + sponsor prizes — make it load-bearing, not name-dropped)
- **Gemini (Google DeepMind)** — image editing + reasoning about what to move.
- **LangChain** — orchestrates the analyze → propose → edit → re-score → branch loop.
- **Pinecone** — memory of winning ad patterns / brand guidelines; RAG to ground suggestions.
- **Clerk** — auth + team/brand workspaces.
- **Sendblue** — (stretch) send variants for approval over iMessage.

## Key technical facts (see HACKATHON_CONTEXT.md for sources)
- Models: **github.com/matthias-k/DeepGaze** (PyTorch, pretrained).
- **DeepGaze IIE** = saliency *heatmap* → use as the **optimization objective / score**.
- **DeepGaze III** = *scanpath* (gaze-path nodes) → use as the **hero visualization**.
- **Both models require a `centerbias` input** (MIT1003 centerbias file, or uniform fallback).
- Deps: PyTorch, NumPy, SciPy. Model weights are git-ignored — download at runtime.

## Task tracks (parallelize)
- **A — Vision/Scoring:** DeepGaze IIE heatmap + III scanpath + define attention metric.
- **B — Agent loop:** Gemini edit wrapper + LangChain optimize loop + branching (stretch).
- **C — Interface:** upload + canvas, heatmap/node overlay, before/after score display.

## Conventions
- Keep secrets in `.env` (git-ignored); commit a `.env.example` with key *names* only.
- Don't commit model weights (`*.pth/*.pt`) — they're git-ignored; fetch at runtime.
- Prefer small modules so the two agents can own different files without colliding.
