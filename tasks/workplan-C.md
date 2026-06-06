# Workplan — Instance C (Frontend / Visuals / Voice)

> **Pixel** — a gaze-driven ad optimizer. Upload a real ad → DeepGaze predicts where eyes look (saliency heatmap + attention score on a target region) → a fleet of AI agents (Gemini "Nano Banana") edits the image to pull attention toward the brand target → re-score → show the number went **UP** (the money shot). Demos at **3pm today**. ~3 hours left, **mock-first**.
>
> **Primary judging track:** Best Multi-Agent Interface — agents visibly collaborating in a unified workspace.

---

## Task Understanding & Success Criteria

**Instance C owns the entire frontend** (Vite + React + TypeScript + React Flow, dark demo theme, state via `useState` in `App.tsx`). We consume the frozen API contract via `api.ts` (with a `USE_MOCK` flag flipping between `mock.json` and live endpoints through the Vite proxy). We do **not** own the backend; we build mock-first so every visual is buildable before A's `/predict` and B's `/agents` land.

The narrative we must make land in 90s: upload a Coca-Cola ad → heatmap shows attention wasted on the model's face, only **12%** on the can → hit **Optimize** → the agent canvas lights up ("checked what Pepsi does well") → optimized image + re-score: can attention **12% → 41%** → (stretch) approve via voice.

### Frontend deliverables → scorecard mapping

Dimensions Instance C most influences: **User Experience (15), Presentation (5), Category / Multi-Agent Interface (20), Innovation (10), Execution (20).**

| Deliverable | UX (15) | Presentation (5) | Multi-Agent Interface (20) | Innovation (10) | Execution (20) |
|---|---|---|---|---|---|
| **AgentFlow** (React Flow canvas, 6 nodes lighting up sequentially + parallel feeders) | ● | ● | ●●● **primary** | ● | ● |
| **HeatmapWipe** (before/after wipe slider — the money shot) | ●● | ●●● | | ● | ●● |
| **ScoreCounter** (animated 12% → 41% count-up + delta pill) | ●● | ●●● | | | ●● |
| **Distractors** (red "attention thieves" callouts) | ●● | ● | | | ● |
| **Scanpath dots** (numbered gaze path, cheap depth) | ● | ● | | ● | ● |
| **Demo state machine** (`phase` + `liveAgent` sequential stagger) | ●● | | ●●● | | ●● |
| **Voice** (push-to-talk approve / commands — stretch) | ● | | ● | ●●● | |
| **Mode B** (type a company → generate ad — stretch) | ● | | | ●●● | ● |
| **Clerk auth fix + don't-block guard** | | | | | ●●● **unblocks all** |
| **Mock → live integration** (per-endpoint flip, proxy, parity) | | | | | ●●● |

**Definition of done (demo-ready):** app boots with no Clerk key; upload → Analyze shows heatmap + distractors + scanpath + ScoreCounter at 12%; Optimize lights up AgentFlow sequentially, then HeatmapWipe reveals after and ScoreCounter jumps to 41%; runs end-to-end in mock; flips per-endpoint to live without structural change.

---

## Architecture

### Component tree

```
main.tsx
 └─ [ClerkProvider if VITE_CLERK_PUBLISHABLE_KEY present, else bare]
     └─ App
        ├─ Header        (title · [MOCK/LIVE badge] · mode toggle · auth corner)
        ├─ Controls      (Upload/Generate toggle · file|company input · brand · Analyze · Optimize · status)
        ├─ Stage (grid: 1fr 340px)
        │   ├─ .canvas (stage-left, the ad — position:relative .frame)
        │   │   ├─ HeatmapWipe   (after phase==="done"; else static image + HeatmapOverlay)
        │   │   ├─ TargetBox     (existing)
        │   │   ├─ Distractors   (red callouts, overlays before-frame)
        │   │   └─ Scanpath dots (numbered, faint connectors)
        │   └─ .panel (stage-right, the proof)
        │       ├─ ScoreCounter  (big animated %, delta pill)
        │       └─ Voice         (approve / commands — stretch)
        └─ .flow (region E, full width, grid-column 1/-1, ~280–320px)
            └─ AgentFlow
                ├─ AgentNode ×6  (custom React Flow node)
                └─ VariantTree   (stretch; only if branches?.length)
```

Shared helper: **`CssHeatmap({ pred })`** — lift the CSS-gradient logic out of `App.tsx`'s `HeatmapOverlay` and export it, so `HeatmapWipe` reuses it instead of duplicating gradient math (avoids drift between the two heatmaps judges compare).

### State: App vs components

**Lives in `App.tsx` (`useState`, single source of truth):**

```ts
// inputs
file: File | null
imgUrl: string                 // object URL OR generated data URL
brand: string                  // "Coca-Cola"
// Mode B
mode: "upload" | "generate"
company: string
// results (from contract)
pred: PredictResult | null
agents: AgentsResult | null
// demo orchestration
phase: "empty"|"uploaded"|"analyzing"|"analyzed"|"optimizing"|"done"
liveAgent: string | null       // which agent node is "running" right now
runtimeMock: "mock" | "live"   // header toggle override (default mock)
```

Derived (no state): `score`, `isBusy = phase==="analyzing"||"optimizing"`, `showWipe = phase==="done"`.

**Lives in components (local UI only):**
- `AgentFlow`: `cursor` (timeline tick), React Flow `nodes`/`edges` via `useNodesState`/`useEdgesState`, memoized `timeline`.
- `HeatmapWipe`: `pos` (0..100 wipe %), `dragging`, `frameRef`.
- `ScoreCounter`: `val` (current displayed score), `rafRef`.
- `Voice`: `state` machine (`idle|listening|speaking|unsupported`), `transcript`, `recRef`.
- `Distractors`: none (optional `hovered`).

### Data flow (frozen contract)

```
POST /predict  → { width, height, attention_score(0..1), heatmap_png(dataURL,""=CSS fallback),
                   target_box[x,y,w,h norm], scanpath[{x,y,order}],
                   distractors[{region:[x,y,w,h], share, desc}] }
                 → pred → HeatmapOverlay/CssHeatmap, TargetBox, Distractors, Scanpath, ScoreCounter(0→12%)

POST /edit     → { variant_png(dataURL), edit_description, width, height }
                 (optional single-edit fallback; core flow uses /agents' variant_png)

POST /agents   → { baseline_score, final_score, delta, brand_brief,
                   competitive_insights{tactics[]}, heatmap_before, heatmap_after,
                   variant_png, rationale, iterations:[{agent, status, summary}] }
                 → agents → AgentFlow (iterations), HeatmapWipe (before/after/variant),
                   ScoreCounter(12%→41%), rationale caption, Voice readback
```

**Mock-mode rule (true on stage):** every backend image field (`heatmap_png`, `heatmap_before`, `heatmap_after`, `variant_png`) is `""`. Fall back to `imgUrl` for images and `<CssHeatmap pred={pred}/>` for heat. These fallbacks are the **primary** render path judges see — build and polish them first, guard every `*_png` on truthiness.

---

## Build Workflow & Sequence

Ordered phases for the remaining ~3 hours. Everything except the live flip is **mock-buildable now**; only the final rehearsal depends on backend.

| Time | Phase | Mock-buildable? | Notes |
|---|---|---|---|
| **0:00–0:20** | **Clerk fix** — uninstall `@clerk/react`, install `@clerk/clerk-react@^5`, patch `main.tsx` (guard, don't throw) + `App.tsx` (correct components). Confirm `npm run dev` boots with **no key**. | ✅ | **Do first — app currently throws on boot.** Unblocks all dev. |
| **0:20–0:50** | **Demo state machine** — replace `busy:string` with `phase`; add `liveAgent`; the `sleep`-stagger `optimize()`; gate ScoreCounter on `phase==="done"`. | ✅ | Backbone for every visual beat. Pure mock. |
| **0:50–1:30** | **AgentFlow** (React Flow) — 6 nodes, edges, custom `AgentNode`, timeline driver, glow on `liveAgent`/`cursor`. Full-width region E. | ✅ | The judged track. Highest score-per-minute. |
| **1:30–2:00** | **ScoreCounter** (rAF count-up) + **HeatmapWipe** (clip-path slider) in stage. | ✅ | The money shot — 12% → 41% must feel earned. |
| **2:00–2:20** | **Scanpath dots** + **Distractors** callout polish + rationale caption + `CssHeatmap` extraction. | ✅ | Cheap depth from data already received. |
| **2:20–2:40** | **Voice** (Web Speech) + **Mode B** front door. Stretch — timebox hard. | ✅ | Narrative closer + innovation points. Cut if behind. |
| **2:40–3:00** | **Live flip + rehearsal** — set per-endpoint flags as A/B confirm; run full 90s on real Coke ad; keep mock as fallback toggle. | Needs backend | Mock-first means never blocked; this is just the swap + dry run. |

**Mock → live flip (high level — full detail in Integration Plan):** `USE_MOCK` is the master switch in `api.ts`. Make it per-endpoint (`USE_MOCK_PREDICT`, `USE_MOCK_AGENTS`) so `/predict` can go live while `/agents` stays mock — matches the order A/B endpoints land. The data shape is identical mock vs live, so the stagger/wipe/counter need zero structural change.

---

## Component Specs

> All components live in `frontend/src/components/`, consume types from `../api`, and reuse the `.frame` convention (absolutely-positioned overlays inside a `position:relative` parent, percentages for normalized coords). Relevant files: `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/mock.json`, `frontend/src/index.css`, `frontend/src/vite-env.d.ts`.

### AgentFlow — `components/AgentFlow.tsx`

The centerpiece for the Multi-Agent Interface track. Renders the 6 agents as a live graph driven **entirely** by `AgentsResult.iterations[]` (no new backend fields), replaying them with sequential + parallel "lighting up" so judges *see* collaboration. Target ~60–90 min on `reactflow@11`.

**Contract reality:**
- `iterations[]` is a **flat, ordered** array of `{ agent, status, summary? }`. In mock all are `status:"done"` and **`Eye` appears twice** (baseline score + re-score). Map agent name → **one fixed node** (case-insensitive); one Eye node re-lit on its second tick; synthesize the running/parallel animation the flat list doesn't encode.
- **No `variant_tree`/`Judge` data in the contract.** Branching is purely stretch: gate it behind the optional additive prop `branches?` (or a tolerated `agents.variant_tree as any`). Never block core flow on it.
- `status` is a free string — normalize: `done|complete|ok → done`, `error|failed → error`, `running|active → running`, else `idle`.

**Props (typed):**
```ts
import type { AgentsResult, AgentStep } from "../api";

export type Variant = { id:string; png:string; eyeScore:number; judgeScore:number; chosen?:boolean; edit?:string };
export type VariantRound = { round:number; variants:Variant[] };

export type AgentFlowProps = {
  agents: AgentsResult | null;   // null → all-idle skeleton graph (the "before" beat)
  branches?: VariantRound[];     // stretch; if present, Judge node + tree panel appear
  autoplayMs?: number;           // step interval; default 650
  onReplay?: () => void;
};

const AGENTS = ["Director","Insider","Scout","Eye","Retoucher","Judge"] as const;
type AgentName = typeof AGENTS[number];
type NodeStatus = "idle" | "running" | "done" | "error";
```

**Node visual states** (custom node; CSS keyframes, no JS rAF):

| status | border | fill | extra |
|---|---|---|---|
| idle | `#3a3a44` 1px | `#1c1c22` | dim, opacity .6 |
| running | `#f5c542` 2px | `#26241a` | `pulse 1s infinite` + spinner dot |
| done | `#27c08a` 2px | `#10241d` | green check, one-shot `flash` on transition |
| error | `#ff5d5d` 2px | `#2a1414` | `!` glyph |

```css
@keyframes pulse { 0%,100%{box-shadow:0 0 0 0 rgba(245,197,66,0)} 50%{box-shadow:0 0 0 8px rgba(245,197,66,.18)} }
@keyframes flash { 0%{transform:scale(1)} 40%{transform:scale(1.06)} 100%{transform:scale(1)} }
```

**Step-driver (flat list → sequential + parallel firing) — the heart of the effect:**
```ts
// Group consecutive feeders (Insider/Scout/Eye) into one parallel tick; rest sequential.
const FEEDERS = new Set(["insider","scout","eye"]);
function buildTimeline(iters: AgentStep[]) {
  let tick = -1, lastWasFeeder = false;
  return iters.map((s) => {
    const isFeeder = FEEDERS.has(s.agent.toLowerCase());
    if (!(isFeeder && lastWasFeeder)) tick++;
    lastWasFeeder = isFeeder;
    return { ...s, tick };
  });
}
```
Driver: `const [cursor,setCursor]=useState(0)`; a `useEffect` with `setInterval(autoplayMs)` increments `cursor` until `cursor > maxTick`, then clears. `onReplay` resets to 0.

Per-node status:
```ts
function statusFor(node: AgentName, cursor: number, timeline: Tick[]): NodeStatus {
  const mine = timeline.filter(t => t.agent.toLowerCase() === node.toLowerCase());
  if (!mine.length) return "idle";
  if (mine.some(t => t.tick === cursor))
    return mine.some(t => norm(t.status)==="error") ? "error" : "running";
  if (mine.some(t => t.tick < cursor))
    return mine.some(t => norm(t.status)==="error") ? "error" : "done";
  return "idle";
}
```
**Director special-case:** running on tick 0 + the Director tick, done after. **Edge animation for free:** an edge is `animated` when its *source* node is `done` AND its *target* node is `running` (data flowing now); else solid/dim.

> **Note — two ways to drive the animation, pick one:** (a) AgentFlow's own internal `cursor`/`setInterval` timeline (self-contained), **or** (b) App's `liveAgent` stagger from the state machine. They overlap — use App's `liveAgent` as the single driver (one node `running` at a time, simplest, matches the narrative) and let AgentFlow read `liveAgent` to set node status; keep the internal `cursor` only for standalone `onReplay`. Don't run both at once.

**Layout** (fixed positions, no auto-layout): Director center; feeders left firing in; pipeline flows right.
```
        Insider ─┐
        Scout  ──┤→ Director → Retoucher → Eye(re-score)
        Eye    ──┘                              │
                                            (Judge)  ← only if branches?
```
```ts
const POS: Record<AgentName,{x:number;y:number}> = {
  Insider:{x:0,y:0}, Scout:{x:0,y:110}, Eye:{x:0,y:220},
  Director:{x:230,y:110}, Retoucher:{x:460,y:110}, Judge:{x:690,y:110},
};
const baseEdges = [
  {id:"i-d",source:"Insider",target:"Director"}, {id:"s-d",source:"Scout",target:"Director"},
  {id:"e-d",source:"Eye",target:"Director"}, {id:"d-r",source:"Director",target:"Retoucher"},
  {id:"r-e",source:"Retoucher",target:"Eye"}, // re-score loop
];
const judgeEdge = {id:"r-j",source:"Retoucher",target:"Judge"}; // push only if branches?.length
```
RF setup: `nodeTypes={{ agent: AgentNode }}`, `fitView`, `panOnDrag={false}`, `nodesDraggable={false}`, dark `<Background variant="dots" />`. **Container needs explicit height (~320px) or RF renders 0px.**

**Custom node** `AgentNode` (~180×84px, rounded 10px, font 12/11):
```tsx
import { Handle, Position, type NodeProps } from "reactflow";
const ICON: Record<string,string> = { Director:"🎬",Insider:"🏷️",Scout:"🔭",Eye:"👁️",Retoucher:"🎨",Judge:"⚖️" };
function AgentNode({ data }: NodeProps) {
  return (
    <div className={`agent-node ${data.status}`}>
      <Handle type="target" position={Position.Left} />
      <div className="an-head"><span className="an-icon">{ICON[data.label]}</span><b>{data.label}</b>
        <span className="an-badge">{data.status}</span></div>
      <div className="an-role">{data.role}</div>
      {data.summary && data.status!=="idle" && <div className="an-sum">{data.summary}</div>}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
```
Static `role` strings (so idle graph reads well): Director="orchestrator", Insider="brand brief", Scout="competitor RAG", Eye="DeepGaze scoring", Retoucher="Gemini edit", Judge="scores variants". `summary` comes from the matching `iterations[]` entry once the node fires.

**Build checklist:**
1. Skeleton + layout (15m): confirm `import ReactFlow,{Background,useNodesState,useEdgesState} from "reactflow"; import "reactflow/dist/style.css";`. 6 static nodes + base edges, default node, `fitView`, 320px container. Verify graph shows.
2. Custom node + CSS states (20m): `AgentNode`, `nodeTypes`, 4 status classes + `pulse`/`flash`. Hardcode a status per node to eyeball.
3. Timeline + driver (20m): read `liveAgent` (or `buildTimeline`+`cursor`), `statusFor()`, recompute nodes via `useMemo`→`setNodes` on change; set edge `animated`. Watch it play through mock (feeders parallel, then sequential).
4. Wire into App (10m): replace the plain-list pipeline with `<AgentFlow agents={agents} ... />`. Keep `rationale` caption beneath.
5. Polish (10m): done-flash, "Replay" button, echo `12% → 41%` near the Eye node, dark Background dots.
6. Stretch — variant tree (15m): `branches` prop + Judge node/edge + `.variant-tree` panel rendered **below** the flow (not inside RF), feed a hardcoded 3×3 ascending array to demo.

### HeatmapWipe — `components/HeatmapWipe.tsx`

The money shot. One frame, drag a vertical handle to wipe from (original ad + `heatmap_before`) to (variant + `heatmap_after`).

**Props:**
```ts
type HeatmapWipeProps = {
  agents: AgentsResult;   // heatmap_before, heatmap_after, variant_png ("" in mock)
  pred: PredictResult;    // distractors → drives CSS heatmap fallback
  imgUrl: string;         // uploaded image object URL — the "" fallback for both sides
};
```
**State:** `pos` (0..100, % from left, default 50), `dragging` (bool), `frameRef` (for pointer-x → % math).

**Resolved sources** (compute once so mock + live both work):
```ts
const beforeImg  = imgUrl;                       // original is always the upload
const afterImg   = agents.variant_png || imgUrl; // mock → reuse upload
const beforeHeat = agents.heatmap_before;        // "" → render <CssHeatmap>
const afterHeat  = agents.heatmap_after;
```
**Layout (clip-path):** `.frame` relative; two full-size absolutely-positioned stacked layers:
- AFTER layer (bottom of z-stack, full): `afterImg` + (`afterHeat ? <img className="heat" src/> : <CssHeatmap pred/>`).
- BEFORE layer (on top, clipped): `beforeImg` + before heat, wrapped in `clipPath: inset(0 ${100-pos}% 0 0)` → reveals left `pos`%.
- Handle: 2px vertical divider at `left:${pos}%` with round grip; "BEFORE 12%" / "AFTER 41%" pills pinned top-left/top-right.

**Build checklist:**
1. Render the two stacked layers inside `frameRef`; AFTER full, BEFORE in the `clip-path: inset()` div driven by `pos`.
2. Each layer's heatmap: `heat ? <img className="heat" src={heat}/> : <CssHeatmap pred={pred}/>` (the CSS path is what judges see — make it pop).
3. Pointer handlers on the frame: `onPointerDown`→set `dragging`; `onPointerMove` (guard on `dragging`) compute `pos = clamp(((e.clientX-rect.left)/rect.width)*100,0,100)` via `getBoundingClientRect()`; `onPointerUp`→clear. Add `touch-action:none` on the frame.
4. Draw divider + grip at `left:${pos}%` and the BEFORE/AFTER score pills.
5. On mount, animate `pos` 100→50 once (short rAF tween or CSS transition on first paint) so the reveal auto-plays, then hand control to the user.

### ScoreCounter — `components/ScoreCounter.tsx`

Big number tweening `baseline_score → final_score` when agents complete, with a highlighted delta.

**Props:**
```ts
type ScoreCounterProps = {
  from: number;   // baseline_score (0..1)
  to: number;     // final_score (0..1)
  delta: number;  // agents.delta (0..1)
  active: boolean;// true once the run is DONE → triggers the run (gate on phase==="done")
  durationMs?: number; // default 1400
};
```
**State:** `val` (current displayed 0..1, init `from`), `rafRef`.

**Animation (rAF + easeOutCubic):**
```ts
useEffect(() => {
  if (!active) return;
  const start = performance.now();
  const ease = (t:number) => 1 - Math.pow(1 - t, 3);
  const tick = (now:number) => {
    const t = Math.min((now - start) / (durationMs ?? 1400), 1);
    setVal(from + (to - from) * ease(t));
    if (t < 1) rafRef.current = requestAnimationFrame(tick);
  };
  rafRef.current = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(rafRef.current!);
}, [active, from, to, durationMs]);
```
**Render:** big `{Math.round(val*100)}%`, label "attention on target"; delta pill `▲ +{Math.round(delta*100)} pts` (green, one-shot pop/scale-in when `val` reaches `to`); `font-variant-numeric: tabular-nums` so digits don't jitter.

> **Two-stage scoring:** show `0 → 12%` on Analyze (`active` when `pred` lands, `from=0 to=pred.attention_score`), then **hold at 12%** through `optimizing`, then `12% → 41%` only on `phase==="done"` (`from=baseline_score to=final_score`). Holding the suspense — the jump is the money shot.

**Build checklist:**
1. Static markup (big `%`, label, delta pill).
2. rAF `useEffect` keyed on `active`; cancel on cleanup.
3. Drop into App's right panel replacing the static `.score` block; pass `from`/`to`/`delta`/`active`.
4. tabular-nums + one-shot scale/glow keyframe on the delta pill for the punch.

### Distractors — `components/Distractors.tsx`

Red labeled callout boxes over each `distractor.region` — the "attention wasted here" beat. Renders inside the existing `position:relative` `.frame` (like `TargetBox`).

**Props:**
```ts
type DistractorsProps = {
  distractors: Distractor[]; // { region:[x,y,w,h] normalized, share, desc }
  show?: boolean;            // default true
};
```
**State:** none (optional `hovered: number|null` to dim others on hover).

**Render:**
```tsx
distractors.map((d, i) => {
  const [x,y,w,h] = d.region;
  return (
    <div key={i} className="distractor"
      style={{ left:`${x*100}%`, top:`${y*100}%`, width:`${w*100}%`, height:`${h*100}%` }}>
      <span className="distractor-label">{d.desc} · {Math.round(d.share*100)}%</span>
    </div>
  );
});
```
**CSS:** `.distractor` `{ position:absolute; border:2px solid #ff3b30; border-radius:4px; background:rgba(255,59,48,.12) }`. `.distractor-label` pinned top-left, `translateY(-100%)`, red bg / white text, tiny radius. **`pointer-events:none`** so it never blocks the wipe handle underneath.

**Build checklist:**
1. Map `distractors` to absolute boxes using `region` percents (mirror `TargetBox`).
2. Red label pill above each box: `desc · share%`.
3. CSS + `pointer-events:none`.
4. In App, render inside the same `.frame` as `TargetBox`: `{pred && <Distractors distractors={pred.distractors} />}`.
5. (Optional) staggered fade/scale-in via `animation-delay:${i*120}ms` — reads as the Eye agent "finding" thieves one-by-one.

### Voice — `components/Voice.tsx` (stretch)

Push-to-talk via Web Speech API: `SpeechRecognition` (STT, Chrome/Edge via `webkitSpeechRecognition`) + `speechSynthesis` (TTS). Thin overlay — never blocks Analyze/Optimize, which still work by click.

**Props:**
```ts
export type VoiceProps = {
  onSetBrand: (brand: string) => void;  // → App setBrand
  onAnalyze: () => void;                // → App analyze()
  onOptimize: () => void;               // → App optimize()
  speakText?: string;                   // AgentsResult.rationale; auto-speaks on change
  disabled?: boolean;                   // App's isBusy
};
type VoiceState = "idle" | "listening" | "speaking" | "unsupported";
```
**State:** `state`, `transcript` (live interim), `recRef`, `supported` (feature-detect once).

**Type shim** (Web Speech isn't in stock DOM lib; add to `vite-env.d.ts`):
```ts
interface Window {
  webkitSpeechRecognition: typeof SpeechRecognition;
  SpeechRecognition: typeof SpeechRecognition;
}
```
**State machine:** `idle` → press → `listening` (`continuous=false`, `interimResults=true`, `lang="en-US"`); `onresult` final → route → `idle`; release / `onend` / `onerror` → `idle` (idempotent). `speakText` non-empty → `speaking` (chunk + speak), → `idle` on last utterance. `unsupported` is terminal (greyed pill, "Voice needs Chrome"). Guard each transition on current `state`.

**Routing (dumb-simple):**
```ts
function route(text: string) {
  const t = text.toLowerCase().trim();
  if (/\b(optimi[sz]e|fix it|make it better|go)\b/.test(t)) return onOptimize();
  if (/\b(analy[sz]e|score|where do (people|they) look)\b/.test(t)) return onAnalyze();
  const m = t.match(/(?:brand(?: is| to)?|set brand(?: to)?|use)\s+(.+)/);
  if (m) return onSetBrand(titleCase(m[1]));
  // free-form /ask is stretch — never on the critical path
}
```
**TTS chunking** (Chrome stalls on long strings — split on sentence boundaries, queue):
```ts
function speak(text: string) {
  window.speechSynthesis.cancel();
  const chunks = text.match(/[^.!?]+[.!?]?/g) ?? [text];
  chunks.forEach((c, i) => {
    const u = new SpeechSynthesisUtterance(c.trim());
    u.rate = 1.05;
    if (i === chunks.length - 1) u.onend = () => setState("idle");
    window.speechSynthesis.speak(u);
  });
  setState("speaking");
}
```
Always `speechSynthesis.cancel()` before recognition and before a new `speak()` so the mic doesn't capture TTS. Trigger the mic-permission prompt once before the demo.

**Build checklist (~45m):**
1. Add the `Window` type shim to `vite-env.d.ts`.
2. Create `Voice.tsx`: state machine + round mic button (grey idle / red pulsing listening / blue speaking) + transcript pill.
3. `startListening` / `onresult` / `route`.
4. `speak` chunking + `useEffect([speakText])` auto-readback.
5. `supported` guard + `unsupported` render.
6. Drop into `.controls` (after Optimize): `<Voice onSetBrand={setBrand} onAnalyze={analyze} onOptimize={optimize} speakText={agents?.rationale} disabled={isBusy} />`.
7. Test in Chrome: "analyze", "optimize", "set brand to Pepsi"; confirm rationale reads back.

### Mode B toggle (Generate front door) — App.tsx + api.ts (stretch)

Mode A = upload (current, default, safe path). Mode B = type a company → `/generate` → returned image becomes the **same** `file`/`imgUrl` the gaze loop already consumes. Everything downstream is untouched.

**`api.ts` addition:**
```ts
export type GenerateResult = { image_png: string; width: number; height: number };
export async function generateAd(company: string): Promise<GenerateResult> {
  if (USE_MOCK) return (mock as any).generate as GenerateResult; // pre-cached data URL
  const r = await fetch("/generate", { method:"POST",
    headers:{ "Content-Type":"application/json" }, body: JSON.stringify({ company }) });
  if (!r.ok) throw new Error(`/generate ${r.status}`);
  return r.json();
}
```
Add a `"generate"` key to `mock.json` holding a real data-URL of a pre-made Coca-Cola ad so Mode B demos instantly with no backend.

**App state:** `mode: "upload"|"generate"`, `company: string`.

**Convert generated data-URL → File** (loop keys off `file: File` — zero downstream change):
```ts
async function onGenerate() {
  if (!company.trim()) return;
  setPhase("uploaded"); // or busy
  try {
    const g = await generateAd(company.trim());
    const f = await dataUrlToFile(g.image_png, `${company}.png`);
    setFile(f); setImgUrl(g.image_png); setBrand(company.trim());
    setPred(null); setAgents(null);
  } catch (e) { alert(String(e)); }
}
async function dataUrlToFile(dataUrl: string, name: string): Promise<File> {
  const blob = await (await fetch(dataUrl)).blob();
  return new File([blob], name, { type: blob.type || "image/png" });
}
```
**UI** (segmented toggle inside `.controls`): Upload | Generate; Upload → file input, Generate → company text input + "Generate ad" button. Brand input, Analyze, Optimize unchanged.

**Build checklist (~25m):**
1. `GenerateResult` + `generateAd` in `api.ts`; pre-cached `"generate"` data-URL in `mock.json`.
2. `mode`/`company` state + `onGenerate` + `dataUrlToFile` in App.
3. Replace file `<input>` with mode toggle + conditional input.
4. CSS for `.modeToggle`/`.on` (tiny segmented control).
5. Test mock: Generate → Analyze → Optimize end-to-end on the generated image.

### App shell

Single-screen, max-width 1200px, dark theme. Recompose into 5 regions so the agent canvas is the hero.

```
HEADER:   Pixel · tagline · [MOCK/LIVE] · mode toggle · auth corner   (region A)
CONTROLS: upload/generate · brand · Analyze · Optimize · status        (region B)
STAGE:    .canvas (HeatmapWipe + TargetBox + Distractors + Scanpath)   (region C, left)
          .panel  (ScoreCounter + delta chip + Voice)                  (region D, right)
FLOW:     AgentFlow — React Flow, 6 nodes, full width                   (region E)
```
**CSS change (minimal):** keep `.stage` as `1fr 340px`; add sibling `.flow { grid-column: 1 / -1; height: 280px; }`. One new rule, no restructure. Move the plain-list "Agent pipeline" out of the panel into AgentFlow nodes; keep `rationale` as a caption under the canvas.

**The sequential-lighting trick** (single response → live collaboration): on entering `optimizing`, don't await-then-dump — stagger.
```ts
async function optimize() {
  setPhase("optimizing");
  const result = await runAgents(file!, brand);   // fires immediately
  for (const step of result.iterations) {          // ~700ms apart
    setLiveAgent(step.agent);
    await sleep(700);
  }
  setAgents(result);
  setLiveAgent(null);
  setPhase("done");                                 // unlocks wipe + 41% count-up
}
```
~5 iterations × 700ms ≈ 3.5s of visible collaboration — perfect for the narrative window. ScoreCounter must NOT jump to 41% until `phase==="done"`.

**Demo state machine transitions:**

| From → To | Trigger | UI effect |
|---|---|---|
| empty → uploaded | onPick/onGenerate sets file | Image shows; Analyze enabled; reset pred/agents |
| uploaded → analyzing | click Analyze | Controls disabled; "reading the image" shimmer |
| analyzing → analyzed | predict() resolves | Heatmap fades in; ScoreCounter 0→12%; distractors; scanpath; Optimize becomes primary CTA |
| analyzed → optimizing | click Optimize | AgentFlow focus; nodes light sequentially via liveAgent |
| optimizing → done | runAgents() resolves AND node animation finishes | HeatmapWipe swaps before→after; ScoreCounter 12%→41%; rationale caption; Voice approve |
| any → empty | new upload | full reset |

---

## Clerk Auth

Three real bugs in current code; fix all three, make auth **optional** so it can never block the 3pm demo.

1. **Wrong package.** Code imports `@clerk/react` (`package.json` has `@clerk/react@6.7.3`). The stable, well-documented Vite+React SDK is **`@clerk/clerk-react` (5.x)**, exposing `SignedIn`/`SignedOut`/`UserButton`/`SignInButton`. (Both packages resolve, but the existing `Show when="signed-out"` API does NOT match `@clerk/react`'s distribution — this is the risk. The task brief's `SignedIn`/`SignedOut` guidance is correct; the in-repo `@clerk/react` + `Show` combo is the bug.)
2. **Wrong component API.** `<Show when="signed-out">` is not the public auth-gating API → use `<SignedIn>` / `<SignedOut>`.
3. **Hard throw blocks dev.** `main.tsx` throws if `VITE_CLERK_PUBLISHABLE_KEY` is missing → whole app dead without a key. For a 3pm demo, auth is polish, not a gate.

**Fix A — dependency:**
```bash
cd frontend
npm uninstall @clerk/react
npm install @clerk/clerk-react@^5
```
**Fix B — `main.tsx`: guard, don't throw** (app runs with OR without a key):
```tsx
import { ClerkProvider } from "@clerk/clerk-react";
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

const pk = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;
const tree = <App />;
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {pk
      ? <ClerkProvider publishableKey={pk} afterSignOutUrl="/">{tree}</ClerkProvider>
      : tree}
  </React.StrictMode>
);
```
**Fix C — `App.tsx`: correct components + safe auth corner:**
```tsx
import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/clerk-react";
```
```tsx
<span className="auth">
  <SignedOut><SignInButton mode="modal" /></SignedOut>
  <SignedIn><UserButton afterSignOutUrl="/" /></SignedIn>
</span>
```
These render nothing without a `ClerkProvider`, so the no-key path stays clean. **Extra-safe option:** gate the whole `.auth` span behind `import.meta.env.VITE_CLERK_PUBLISHABLE_KEY` to dodge any "must be inside ClerkProvider" surprise from a given SDK version.

**Env** — add to `.env.example` and local `.env` (only `VITE_`-prefixed vars reach the client — correct):
```
VITE_CLERK_PUBLISHABLE_KEY=
```
Leave blank for the demo; the guard handles it. **Confirm `npm run dev` boots with no key before touching anything else** — AgentFlow and the money-shot components are worthless if the app throws on boot.

---

## Integration Plan

### USE_MOCK flip (per-endpoint)
`api.ts` `USE_MOCK` is the master switch. Make it env-driven and per-endpoint so `/predict` can go live while `/agents` stays mock (matches the order A/B land):
```ts
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false"; // mock unless explicitly off
// or two flags: USE_MOCK_PREDICT, USE_MOCK_AGENTS — check each function independently
```
Ship with mock ON; flip a flag to `false` only once that endpoint is confirmed returning real data. The header **MOCK/LIVE toggle** can drive a runtime override, but the demo-safe default is mock ON.

### Vite proxy
`vite.config.ts` already proxies `/predict`, `/edit`, `/agents` → `VITE_API_BASE` (`localhost:8000`). Correct. Endpoints are multipart `POST` — default proxy handles it; no `changeOrigin` needed for localhost. Going through the proxy is same-origin to the browser, so backend CORS shouldn't be doubly required. Add `/generate` to the proxy list when Mode B goes live.

### Wiring when A/B endpoints land
- **A's `/predict` lands:** flip `USE_MOCK_PREDICT=false`. Real `heatmap_png` data-URL replaces the CSS fallback automatically (`HeatmapOverlay` already branches on `pred.heatmap_png`). Verify `target_box`/`distractors`/`scanpath` normalization renders in-frame. **First live milestone — the heatmap on a real Coke ad.**
- **A's `/edit` lands:** optional for core narrative (the `/agents` path returns the final `variant_png`); wire it for a "manual single edit" fallback button if `/agents` is flaky.
- **B's `/agents` lands:** flip `USE_MOCK_AGENTS=false`. The `liveAgent` stagger + wipe + counter consume `baseline_score`, `final_score`, `iterations`, `heatmap_before/after`, `variant_png`, `rationale` — all already in the contract/types. Same shape as `mock.json`, nothing structural changes.

### Keeping mock.json in sync
- `mock.json` must mirror the contract **exactly** (same keys/shapes the live endpoints return) so the flip is a no-op. Backend image fields (`heatmap_png`, `heatmap_before/after`, `variant_png`) stay `""` in mock → components fall back to `imgUrl` + `CssHeatmap`. Guard every `*_png` render on truthiness, exactly like `HeatmapOverlay` already does.
- `iterations[]` stays flat/ordered with `Eye` twice; add a `"generate"` data-URL key for Mode B; add an optional `branches` array only if demoing the variant tree.
- **Contract sends match:** `predict()` sends multipart `image`; `runAgents` sends `image` + `brand` (optional `target` fine to omit) — both match the contract.

---

## Risks & Cut-Line

**Cut order if behind (drop first → last):**
1. **Mode B (Generate front door)** — pure additive innovation; upload is the safe default path.
2. **Voice** — narrative closer; hard-timebox to 2:20–2:40, cut entirely if AgentFlow/ScoreCounter aren't solid.
3. **Variant tree (Judge branching)** — stretch, gated behind optional prop; no backend data exists. Render nothing if absent.
4. **Scanpath dots** — cheap depth, but skippable.
5. **HeatmapWipe slider** — fall back to a simple before/after cross-fade if the pointer-drag math eats time. Keep *a* before→after reveal.

**Never cut (these carry the track + the money shot):**
- **AgentFlow** — the entire Multi-Agent Interface category (20 pts).
- **ScoreCounter** — the 12% → 41% jump is the money shot (Presentation + Execution).
- **The sequential `liveAgent` stagger** — without it, agents don't *visibly* collaborate.

**Top risks:**
- **Clerk throws on boot** → whole app (and demo) dead. Mitigation: fix package + guard `main.tsx` in the first 20 min; verify boot with no key.
- **React Flow 0px height** → invisible canvas. Mitigation: explicit container height; mandatory `import "reactflow/dist/style.css"`. Use `reactflow` (v11) imports, NOT `@xyflow/react` (v12).
- **Empty `*_png` in mock** → broken images on stage. Mitigation: the `imgUrl` + `CssHeatmap` fallbacks are the *primary* path — build/polish them first.
- **Backend late or flaky** → mock-first means never blocked; keep the MOCK toggle as a live fallback during the demo.
- **Voice STT Chrome-only / mic prompt mid-demo** → feature-detect to `unsupported` (never throw); trigger the permission prompt once before 3pm.

**Files Instance C will touch:** `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/index.css`, `frontend/src/vite-env.d.ts`, `.env.example`; new: `frontend/src/components/AgentFlow.tsx`, `HeatmapWipe.tsx`, `ScoreCounter.tsx`, `Distractors.tsx`, `Voice.tsx`.
