# Tasks — Frontend / Visuals (Instance C)

> Owns `frontend/` + `.env.example`. Build against `mock.json`; per-endpoint live flags in `api.ts`.
> **Submit 3:00 PM · video demo 2:30 PM · ~build until 2:25.** Prioritize what the camera sees.

## ✅ Done (today)
- [x] Vite + React scaffold, typed `api.ts` client + Vite proxy to backend.
- [x] **Light-mode redesign** — "optical instrument" theme, Fraunces/Hanken/Spline fonts, atmosphere.
- [x] **Sample campaign gallery** — 8 real ad images (`public/samples/*.jpg`) + `samples.ts` w/ per-brand target boxes. Click → analyze.
- [x] **Real DeepGaze wired** — `/predict` is LIVE (sends each sample's target box; real heatmap + score render).
- [x] **Animated score count-up** + before→after delta pill.
- [x] **Connected scanpath** — 1→2→3→4 gaze path (drawn line + sequential numbered nodes).
- [x] Distractor "attention thieves" bars; agent pipeline panel from `iterations[]`.
- [x] Clerk auth degrades gracefully (boots to playground w/o key).
- [x] Removed obsolete category screenshots (kept `context.md`).

## 🎯 Must-have before 2:30 (the demo money shot)
1. [ ] **Show the AFTER, not just numbers** (~15 min) — on Optimize, swap the canvas to the optimized image + after-heatmap so the lift is *visible*, not just a counter. Needs a real `variant_png`/`heatmap_after` (see decision A).
2. [ ] **Precompute ONE hero result** (~10 min) — run real `/agents` on the best "misdirected attention" sample now, bake `variant_png` + `heatmap_before/after` + the rising score into `mock.json` so the on-stage click is INSTANT and shows a real edit. Avoids the 65s live wait.
3. [ ] **End-to-end dry run** (~5 min) — click hero sample → real heatmap + scanpath → Optimize → before/after + agent pipeline. Confirm no console errors, images load.

## ✨ Nice-to-have (only if green by ~2:00)
- [ ] **Before/after wipe slider** on the same frame — the signature visual (drag to reveal optimized heatmap).
- [ ] **Agent nodes**, not a list — render the 5 agents (Insider/Scout/Eye/Retoucher/Eye) as connected nodes that light up grey→green. (Full React Flow is risky on time; a CSS node row is the safe version.)

## ⛔ Cut for time (post-submission)
- Voice (Web Speech), Mode-B "type a company", branch tree view, LangSmith chart.

## ❓ Open decisions (need Enes)
- **A. Optimize in the demo:** (1) **mock, instant, dramatic** 12%→41% but fake edit image; (2) **real, true edit + after-heatmap but ~65s** live; (3) **precompute hero → instant AND real** ← recommended.
- **B. Big-lift sample:** current samples are clean product shots (small real lift). Want me to grab a face-vs-logo ad so the optimizer has a real thief to fix?
