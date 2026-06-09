import { useEffect, useRef, useState } from "react";
import { UserButton, SignInButton, Show } from "@clerk/react";
import { predict, optimizeStep, health, USE_MOCK_PREDICT, type PredictResult, type AgentsResult, type TreeNode, type Fixation, type Health } from "./api";
import { SAMPLES, type Sample } from "./samples";
import HeroBranches from "./HeroBranches";
import BranchWorkspace from "./BranchWorkspace";
import ActivityLog from "./ActivityLog";

// UserButton must live inside a ClerkProvider; main.tsx only mounts one when a key exists.
const HAS_CLERK = !!import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

// Download a data-URL image (the finalized optimized creative).
function downloadImage(dataUrl: string, name: string) {
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = `${(name || "pixel").toLowerCase().replace(/\s+/g, "-")}-optimized.png`;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

// Control state for the incremental "one branch at a time" optimizer.
type StepCtl = {
  step: number;          // next branch index (also the directive to try)
  baseline: number;      // original attention score (the headline floor)
  bestScore: number;     // best attention so far
  bestNodeId: number;    // tree id of the current best (parent for the next branch)
  bestImgUrl: string;    // current best creative (data URL / sample URL) to edit next
  running: boolean;      // a branch is generating
  awaiting: boolean;     // paused, waiting for the user to continue/stop
  done: boolean;         // user chose to stop
  exhausted: boolean;    // tried every directive in the pool
  lastImproved: boolean; // did the most recent branch beat the current best?
  lastScore: number;     // most recent branch's attention
  lastJudge: number;     // most recent branch's Judge brand-fit
  lastReason: string;    // why the last branch was kept or rejected (Judge veto / guard flag)
};

async function dataUrlToFile(url: string, name: string): Promise<File> {
  const blob = await (await fetch(url)).blob();
  return new File([blob], name, { type: blob.type || "image/png" });
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [imgUrl, setImgUrl] = useState<string>("");
  const [brand, setBrand] = useState("Coca-Cola");
  const [active, setActive] = useState<Sample | null>(null);
  const [pred, setPred] = useState<PredictResult | null>(null);
  const [agents, setAgents] = useState<AgentsResult | null>(null);
  const [busy, setBusy] = useState<string>("");
  // Incremental "one branch at a time" optimizer control (null = not optimizing).
  const [stepCtl, setStepCtl] = useState<StepCtl | null>(null);
  const [hint, setHint] = useState(""); // optional user suggestion fed to Nano Banana
  const [hp, setHp] = useState<Health | null>(null); // /health → drives the LIVE/DEMO badge

  // Poll /health once on mount so the badge honestly reflects whether the REAL model loaded.
  useEffect(() => { health().then(setHp).catch(() => setHp(null)); }, []);

  function reset() {
    setFile(null); setImgUrl(""); setActive(null); setPred(null); setAgents(null); setStepCtl(null);
  }

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setActive(null); setPred(null); setAgents(null); setStepCtl(null);
    setFile(f); setImgUrl(URL.createObjectURL(f));
  }

  async function loadSample(s: Sample) {
    setBusy("Loading campaign…");
    try {
      const blob = await (await fetch(s.img)).blob();
      const f = new File([blob], `${s.id}.jpg`, { type: blob.type || "image/jpeg" });
      setActive(s); setBrand(s.brand); setAgents(null); setPred(null);
      setFile(f); setImgUrl(s.img);
      setBusy("Analyzing attention…");
      setPred(await predict(f, s.target_box)); // real backend scores attention in the brand's region
    } catch (e) {
      alert(String(e));
    } finally {
      setBusy("");
    }
  }

  async function analyze() {
    if (!file) return;
    setBusy("Analyzing attention…"); setStepCtl(null); setAgents(null);
    try { setPred(await predict(file, active?.target_box)); }
    catch (e) { alert(String(e)); }
    finally { setBusy(""); }
  }

  // Start the incremental optimizer: establish a baseline, seed the tree with the original,
  // then grow ONE branch. After each branch the user decides whether to spawn another.
  async function optimize() {
    if (!file) return;
    let p = pred;
    if (!p) {
      setBusy("Eye · scoring baseline attention…");
      try { p = await predict(file, active?.target_box); setPred(p); }
      catch (e) { alert(String(e)); setBusy(""); return; }
    }
    const baseline = p.attention_score;
    const root: TreeNode = {
      id: 0, parent: null, depth: 0, score: baseline, status: "root",
      directive: "original", image: imgUrl, heatmap: p.heatmap_png || undefined,
    };
    setAgents({
      tree: [root], baseline_score: baseline, final_score: baseline, delta: 0,
      heatmap_before: p.heatmap_png || "", heatmap_after: "", variant_png: "",
      rationale: "", iterations: [],
    });
    const ctl: StepCtl = {
      step: 0, baseline, bestScore: baseline, bestNodeId: 0, bestImgUrl: imgUrl,
      running: false, awaiting: false, done: false, exhausted: false,
      lastImproved: false, lastScore: baseline, lastJudge: 0, lastReason: "",
    };
    setStepCtl(ctl);
    await runBranch(ctl);
  }

  // Grow exactly one branch off the current best, score + judge it, and pause for the user.
  // HONEST: we show the real DeepGaze score the backend returns — a branch that doesn't beat
  // the current best (or that the Judge vetoes / the reward-hack guard flags) is kept in the
  // tree as a failed attempt, NOT adopted, and the headline score does not move for it.
  async function runBranch(ctl: StepCtl) {
    if (!file) return;
    setStepCtl({ ...ctl, running: true, awaiting: false });
    setBusy(`Retoucher · branch ${ctl.step + 1} with Nano Banana…`);
    try {
      const src = ctl.step === 0 ? file : await dataUrlToFile(ctl.bestImgUrl, "best.png");
      const res = await optimizeStep(src, brand, ctl.step, active?.target_box, hint);
      const newScore = res.new_score;          // real size-invariant prominence (can be lower)
      const improved = res.improved;           // real: rose AND not vetoed AND guard accepted
      const becomesBest = improved && newScore > ctl.bestScore;
      const id = ctl.step + 1; // one node per branch -> ids are deterministic
      const node: TreeNode = {
        id, parent: ctl.bestNodeId, depth: ctl.step + 1, score: newScore,
        status: becomesBest ? "best" : "dead", // failed attempts are shown as pruned, not winners
        directive: res.directive, image: res.variant_png,
      };
      const reason = res.vetoed
        ? `Judge vetoed it (brand-fit ${res.judge})`
        : res.guard && res.guard !== "accept"
          ? (res.guard_reasons?.[0] ?? `guard: ${res.guard}`)
          : !improved && newScore <= ctl.bestScore
            ? `didn't beat ${Math.round(ctl.bestScore * 100)}%`
            : "";
      // Only adopt the edit as the new best when it genuinely wins.
      const nextBestScore = becomesBest ? newScore : ctl.bestScore;
      const nextBestNodeId = becomesBest ? id : ctl.bestNodeId;
      const nextBestImgUrl = becomesBest ? res.variant_png : ctl.bestImgUrl;
      setAgents((prev) => {
        if (!prev) return prev;
        let tree = [...(prev.tree ?? []), node];
        // when this branch wins, the previous best becomes an interior "alive" node
        if (becomesBest) {
          tree = tree.map((n) =>
            n.id === ctl.bestNodeId && n.status !== "root" ? { ...n, status: "alive" } : n);
        }
        const summary = becomesBest
          ? `✓ kept · ${Math.round(newScore * 100)}% (+${Math.round((newScore - ctl.baseline) * 100)} pts)`
          : `✕ ${Math.round(newScore * 100)}% — ${reason || "not adopted"}`;
        const iterations = [...prev.iterations, {
          agent: `Branch ${ctl.step + 1}`, status: "done", summary: summary.slice(0, 96),
        }];
        return {
          ...prev, tree, iterations,
          // headline image + score reflect the BEST so far, never a regressing branch
          variant_png: nextBestNodeId === 0 ? "" : nextBestImgUrl,
          final_score: nextBestScore, delta: nextBestScore - ctl.baseline,
        };
      });
      setStepCtl({
        ...ctl, step: ctl.step + 1, running: false, awaiting: true,
        lastImproved: becomesBest, lastScore: newScore, lastJudge: res.judge, lastReason: reason,
        bestScore: nextBestScore, bestNodeId: nextBestNodeId, bestImgUrl: nextBestImgUrl,
        exhausted: ctl.step + 1 >= res.n_directives,
      });
    } catch (e) {
      alert(String(e));
      setStepCtl({ ...ctl, running: false, awaiting: true });
    } finally {
      setBusy("");
    }
  }

  const score = agents?.final_score ?? pred?.attention_score;
  // prefer the picked sample's known target region for the overlay (mock score is generic)
  const targetBox = active?.target_box ?? pred?.target_box;

  return (
    <div className="app">
      <header>
        <span className="brandmark" onClick={reset} role="button" tabIndex={0} title="Home"
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && reset()} style={{ cursor: "pointer" }}>
          <span className="dot" />
          <h1>Pixel</h1>
        </span>
        <span className="spacer" />
        {hp && (
          <span
            className={`modebadge ${hp.deepgaze_loaded ? "live" : "demo"}`}
            title={`engine: ${hp.engine}${hp.device ? " · " + hp.device : ""} · gemini ${hp.gemini ? "on" : "off"}`}
          >
            <span className="md-dot" />
            {hp.deepgaze_loaded ? "LIVE · DeepGaze" : "DEMO · fallback"}
          </span>
        )}
        {HAS_CLERK && (
          <span className="auth">
            <Show when="signed-out">
              <SignInButton mode="modal"><button className="ghost">Log in</button></SignInButton>
            </Show>
            <Show when="signed-in"><UserButton /></Show>
          </span>
        )}
      </header>

      {!imgUrl ? (
        <>
          <section className="hero">
            <div className="hero-copy">
              <p className="eyebrow">Gaze-driven campaign optimizer</p>
              <h2>See where eyes go. <em>Move them</em> to your brand.</h2>
              <p>
                Pick a campaign and Pixel predicts where attention lands, names the thieves
                stealing it, then a team of agents redirects it, proving the lift with a
                before / after attention score.
              </p>
            </div>
            <HeroBranches />
          </section>

          <div className="uploadrow">
            <label className="filebtn">
              ↑ Upload your own ad
              <input type="file" accept="image/*" onChange={onPick} />
            </label>
            <span className="or">or pick a sample below</span>
          </div>

          <div className="gallery-head">
            <h3>Sample campaigns</h3>
            <span className="hint">click one to analyze →</span>
          </div>
          <div className="gallery">
            {SAMPLES.map((s) => (
              <button className="card" key={s.id} onClick={() => loadSample(s)} title={s.target_desc}>
                <span className="thumb">
                  <span className="ph" style={{ background: s.tint }}>{s.brand[0]}</span>
                  <img
                    src={s.img}
                    alt={`${s.brand} — ${s.campaign}`}
                    loading="lazy"
                    decoding="async"
                    onLoad={(e) => ((e.currentTarget.previousElementSibling as HTMLElement).style.display = "none")}
                  />
                  <span className="go">Analyze</span>
                </span>
                <span className="meta">
                  <span className="b"><span className="swatch" style={{ background: s.tint }} />{s.brand}</span>
                  <span className="c">{s.campaign}{s.note ? " ·*" : ""}</span>
                </span>
              </button>
            ))}
          </div>

        </>
      ) : (
        <>
          <div className="controls">
            <label className="filebtn">
              ↑ New image
              <input type="file" accept="image/*" onChange={onPick} />
            </label>
            <span className="field">
              <label>Brand</label>
              <input type="text" value={brand} onChange={(e) => setBrand(e.target.value)} placeholder="Brand"
                autoComplete="off" autoCapitalize="words" spellCheck={false} />
            </span>
            <span className="field">
              <label>Suggestion (optional)</label>
              <input type="text" value={hint} onChange={(e) => setHint(e.target.value)}
                placeholder="tell Nano Banana what to change…" autoComplete="off" spellCheck={false} />
            </span>
            <button onClick={analyze} disabled={!file || !!busy}>Analyze</button>
            <button onClick={optimize} disabled={!file || !!busy} className="primary">Optimize ✦</button>
            {agents?.variant_png && (
              <button onClick={() => downloadImage(agents.variant_png, active?.id ?? brand)}>↓ Download</button>
            )}
            {busy && <span className="busy">{busy}<span className="dots" /></span>}
            <span className="spacer" />
            <button className="ghost" onClick={reset}>← Gallery</button>
          </div>

          <div className="stage">
            <div className="canvas">
              <div className="frame">
                <img className="base" src={agents?.variant_png || imgUrl} alt="campaign" />
                {agents?.heatmap_after ? (
                  <img className="heat" src={agents.heatmap_after} alt="optimized heatmap" />
                ) : (
                  pred && <HeatmapOverlay pred={pred} />
                )}
                {pred && targetBox && <TargetBox box={targetBox} />}
                {!agents && pred?.scanpath && <Scanpath pts={pred.scanpath} />}
                {agents && <span className="frame-badge">✦ optimized</span>}
              </div>
            </div>

            <aside className="panel">
              <ActivityLog busy={busy} pred={pred} agents={agents} />
              {score !== undefined && (
                <div className="score">
                  <div className="num"><Counter value={score * 100} /><span className="pct">%</span></div>
                  <div className="lbl">attention on target</div>
                  <div className="calib" title="ratio of attention density inside the target box to its area share, mapped to 0–100. Size-invariant: it rewards a region that out-pulls its size, not one that is simply larger.">
                    size-invariant prominence · 50 = average
                  </div>
                  {agents && (
                    <div className="delta">
                      <span className="vals">{Math.round(agents.baseline_score * 100)}%</span>
                      <span className="arrow">→</span>
                      <span className="vals">{Math.round(agents.final_score * 100)}%</span>
                      <span className="lift">+{Math.round(agents.delta * 100)} pts</span>
                    </div>
                  )}
                </div>
              )}

              {pred?.distractors?.length ? (
                <div className="block">
                  <h3>Competing for attention</h3>
                  {pred.distractors.map((d, i) => (
                    <div className="row" key={i} style={{ display: "block" }}>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span className="thief">{d.desc}</span>
                        <b>{Math.round(d.share * 100)}%</b>
                      </div>
                      <div className="bar"><i style={{ width: `${Math.min(100, d.share * 100)}%` }} /></div>
                    </div>
                  ))}
                </div>
              ) : null}

              {agents && (
                <div className="block pipe">
                  <h3>Agent pipeline</h3>
                  {agents.iterations.map((s, i) => (
                    <div className="step" key={i}>
                      <span className="ix">{i + 1}</span>
                      <span>
                        <div className="who">{s.agent}</div>
                        <div className="what">{s.summary}</div>
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {active?.note && (
                <p className="rationale" style={{ borderTop: "none", paddingTop: 0 }}>
                  * {active.brand}: {active.note}.
                </p>
              )}
            </aside>
          </div>

          {stepCtl && (stepCtl.running || stepCtl.awaiting) && !stepCtl.done && (
            <div className="branchctl">
              {stepCtl.running ? (
                <span className="bc-msg">Growing branch {stepCtl.step + 1} — Nano Banana is editing…<span className="dots" /></span>
              ) : (
                <>
                  <span className="bc-msg">
                    {stepCtl.lastImproved
                      ? `✓ Branch ${stepCtl.step} kept — attention now ${Math.round(stepCtl.lastScore * 100)}% (+${Math.round((stepCtl.bestScore - stepCtl.baseline) * 100)} pts total)`
                      : `✕ Branch ${stepCtl.step} not adopted — ${Math.round(stepCtl.lastScore * 100)}%${stepCtl.lastReason ? `, ${stepCtl.lastReason}` : ""}`}
                  </span>
                  <span className="spacer" />
                  {stepCtl.exhausted
                    ? <span className="bc-note">all directions explored</span>
                    : <button className="primary" onClick={() => runBranch(stepCtl)}>Spawn another branch ✦</button>}
                  <button className="ghost" onClick={() => setStepCtl({ ...stepCtl, awaiting: false, done: true })}>
                    {stepCtl.bestScore > stepCtl.baseline ? "Stop — use this result" : "Stop"}
                  </button>
                </>
              )}
            </div>
          )}

          {agents?.tree?.length ? (
            <BranchWorkspace tree={agents.tree} baseline={agents.baseline_score} />
          ) : null}
        </>
      )}
    </div>
  );
}

// Animated count-up for the hero score (no dependency; rAF easing).
function Counter({ value }: { value: number }) {
  const [n, setN] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    const start = performance.now();
    const a = from.current, b = value, dur = 650;
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / dur);
      const e = 1 - Math.pow(1 - k, 3); // easeOutCubic
      setN(a + (b - a) * e);
      if (k < 1) raf = requestAnimationFrame(tick);
      else from.current = b;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <>{Math.round(n)}</>;
}

// Heatmap: real PNG from backend, else a CSS-gradient stand-in so mock mode looks alive.
function HeatmapOverlay({ pred }: { pred: PredictResult }) {
  if (pred.heatmap_png) return <img className="heat" src={pred.heatmap_png} alt="attention heatmap" />;
  const blobs = pred.distractors
    .map((d) => {
      const cx = (d.region[0] + d.region[2] / 2) * 100;
      const cy = (d.region[1] + d.region[3] / 2) * 100;
      return `radial-gradient(circle at ${cx}% ${cy}%, rgba(238,61,35,${0.35 + d.share}) 0%, rgba(238,61,35,0) 26%)`;
    })
    .join(",");
  return <div className="heat" style={{ backgroundImage: blobs }} />;
}

// Scanpath: the predicted gaze ORDER. A connected 1→2→3→4 path (line drawn through
// the fixations) with numbered nodes that pop in sequence — "where eyes move, and when".
function Scanpath({ pts }: { pts: Fixation[] }) {
  if (!pts?.length) return null;
  const s = [...pts].sort((a, b) => a.order - b.order);
  const poly = s.map((p) => `${p.x * 100},${p.y * 100}`).join(" ");
  return (
    <>
      <svg className="scan" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <polyline className="scan-line" points={poly} pathLength={1} />
      </svg>
      {s.map((p, i) => (
        <span
          className="scan-dot"
          key={p.order}
          style={{ left: `${p.x * 100}%`, top: `${p.y * 100}%`, animationDelay: `${0.15 + i * 0.13}s` }}
        >
          {p.order}
        </span>
      ))}
    </>
  );
}

function TargetBox({ box }: { box: [number, number, number, number] }) {
  const [x, y, w, h] = box;
  return (
    <div className="target" style={{ left: `${x * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, height: `${h * 100}%` }}>
      <span className="tlabel">target</span>
    </div>
  );
}
