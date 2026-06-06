# Pixel — Agentic Campaign Optimization

> **See where your audience looks. Let agents fix it. Prove the lift.**

Pixel takes a brand's ad creative, predicts where human eyes will actually land using neuroscience-grade gaze models, then orchestrates a team of AI agents — informed by competitor analysis — to redesign the image so attention flows to what matters (logo / product / CTA). Every edit is scored with an **objective before/after attention metric**, so the improvement is provable, not subjective.

Built in one day for **Multimodal Hacks: Build the Interface for Agents** (#NYTechWeek, June 6 2026).
**Target track:** Best Multi-Agent Interface.

---

## The problem
Brands spend millions on creative but can't see where attention goes until after launch. Pixel makes attention visible *and* actionable — before you spend a dollar on media.

## How it works
1. **Upload** an ad image and pick the brand + target region (logo/CTA).
2. **Analyze** — DeepGaze predicts visual attention: a saliency **heatmap** (where eyes go) and a **scanpath** (the order eyes move).
3. **Understand** — a multi-agent team studies the brand and runs **competitive analysis** (e.g. Coca-Cola vs. Pepsi + past ads: what works, what doesn't).
4. **Optimize** — the leader agent fuses gaze gaps + competitor tactics into concrete edits, applied via Gemini image editing.
5. **Re-score** — DeepGaze re-runs; the **attention-on-target score** updates. Keep the winning variant.

## The multi-agent system
A **leader/orchestrator** coordinates four specialists (this is the "interface for agents" story):

| Agent | Job |
|---|---|
| **Brand Understanding** | Brand brief: product, audience, tone, palette, target region |
| **Competitive Analysis** | What competitors + past ads do well/poorly → actionable tactics (RAG over Pinecone) |
| **Gaze Analysis** | Runs DeepGaze, computes attention score + top distractors |
| **Creative Editor** | Turns insights into a concrete edit, applies it via Gemini, triggers re-scoring |

Full spec + data contract: **[PLAN.md](./PLAN.md)**.

## Tech stack
- **Backend:** Python + FastAPI — `/predict` (DeepGaze), `/edit` (Gemini), `/agents` (LangChain).
- **Frontend:** React + Vite + **React Flow** — node canvas renders both the gaze scanpath *and* the live agent pipeline.
- **Gaze models:** DeepGaze IIE (heatmap → score) + DeepGaze III (scanpath nodes), PyTorch CPU.
- **Image editing:** Gemini `gemini-2.5-flash-image` (Nano Banana).
- **Orchestration:** LangChain (sub-agents as tools).

## Sponsor integration
| Sponsor | Role |
|---|---|
| **Google DeepMind / Gemini** | Image editing + agent reasoning |
| **LangChain** | Multi-agent orchestration |
| **Pinecone** | Vector memory of competitor ads / brand guidelines (RAG) |
| **Clerk** | Auth + team workspaces *(optional)* |
| **Sendblue** | iMessage approval of winning variant *(stretch)* |

## Repo layout
```
pixel/
├─ backend/    FastAPI · deepgaze_runner.py · gemini.py · agents.py
├─ frontend/   Vite + React + React Flow
├─ samples/    hero ads + precomputed before/after (demo fallback)
├─ CLAUDE.md             # how agents should work in this repo (read first)
├─ HACKATHON_CONTEXT.md  # event, scoring, strategy
└─ PLAN.md               # architecture spec + technical quickstart + timeline
```

## Quickstart
See **[PLAN.md → Technical Quickstart](./PLAN.md)** for exact install/run commands. Secrets go in `.env` (git-ignored); never commit API keys.
