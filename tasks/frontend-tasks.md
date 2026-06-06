# Tasks — Frontend / Visuals / Voice (Instance C — me)

> **Owns only `frontend/`** + `.env.example`. Never touches `backend/`. Builds against `frontend/src/mock.json` (the frozen contract); flips `USE_MOCK=false` to go live. Commit small + often; **pull/rebase before every push**.

## Done
- [x] Vite + React + React Flow scaffold; dark demo theme.
- [x] `api.ts` typed client matching the frozen contract (`/predict`, `/edit`, `/agents`) with `USE_MOCK` flag + Vite proxy.
- [x] `mock.json` contract-shaped sample (also serves as the live contract reference for A & B).
- [x] App shell: upload → Analyze (heatmap overlay + attention score + distractor list) → Optimize (agent pipeline + before/after delta). CSS-gradient heatmap fallback in mock mode.

## Next (priority order — each is an isolated component, no collisions)
- [ ] **React Flow agent canvas** (`components/AgentFlow.tsx`) — nodes Director / Insider / Scout / Eye / Retoucher (+ Judge). Grey → pulsing → green as `iterations[]` progress. Insider+Scout+Eye fire in parallel, edges converge on Director. *This wins the Multi-Agent Interface track.*
- [ ] **Before/after wipe slider** (`components/HeatmapWipe.tsx`) — drag to wipe between original and optimized heatmap on the same ad. The signature visual.
- [ ] **Animated score counter** — count-up `12% → 41%` with the delta highlighted; trigger on Optimize complete.
- [ ] **Branch tree view** (if B ships branching) — render the variant tree (round → 3 variants → chosen), show DeepGaze + Judge score per node.
- [ ] **Attention-per-iteration chart** — small line chart of the rising score (from `iterations` / LangSmith feedback).
- [ ] **Voice (Web Speech)** (`components/Voice.tsx`) — push-to-talk: `SpeechRecognition` → fill the brand/instruction → call existing endpoint → `speechSynthesis` reads the rationale back. ~45 min; cannot break the core loop (pure wrapper). Hard stop ~2:15.
- [ ] **Mode B front door** — a "type a company instead" input that hits the generate path, then reuses the same optimize UI.
- [ ] **Demo polish** — per-node loading states, distractor callout box on the image, target-region picker, graceful errors.

## Integration checklist
- [ ] When A's `/predict` + `/edit` are live: set `USE_MOCK=false`, verify proxy, confirm heatmap data URLs render.
- [ ] When B's `/agents` is live: confirm the pipeline/canvas animates from real `iterations[]`.
- [ ] Keep `mock.json` in sync if the contract changes (announce contract changes to A & B first).
