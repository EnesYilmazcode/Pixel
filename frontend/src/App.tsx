import { useState } from "react";
import { predict, runAgents, USE_MOCK, type PredictResult, type AgentsResult } from "./api";

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [imgUrl, setImgUrl] = useState<string>("");
  const [brand, setBrand] = useState("Coca-Cola");
  const [pred, setPred] = useState<PredictResult | null>(null);
  const [agents, setAgents] = useState<AgentsResult | null>(null);
  const [busy, setBusy] = useState<string>("");

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setImgUrl(URL.createObjectURL(f));
    setPred(null);
    setAgents(null);
  }

  async function analyze() {
    if (!file) return;
    setBusy("Analyzing attention…");
    try {
      setPred(await predict(file));
    } catch (e) {
      alert(String(e));
    } finally {
      setBusy("");
    }
  }

  async function optimize() {
    if (!file) return;
    setBusy("Agents optimizing…");
    try {
      setAgents(await runAgents(file, brand));
    } catch (e) {
      alert(String(e));
    } finally {
      setBusy("");
    }
  }

  const score = agents?.final_score ?? pred?.attention_score;

  return (
    <div className="app">
      <header>
        <h1>Pixel</h1>
        <span className="tag">see where attention goes · fix it · prove the lift</span>
        {USE_MOCK && <span className="mock">MOCK DATA</span>}
      </header>

      <div className="controls">
        <input type="file" accept="image/*" onChange={onPick} />
        <input value={brand} onChange={(e) => setBrand(e.target.value)} placeholder="Brand" />
        <button onClick={analyze} disabled={!file || !!busy}>Analyze</button>
        <button onClick={optimize} disabled={!file || !!busy} className="primary">Optimize</button>
        {busy && <span className="busy">{busy}</span>}
      </div>

      <div className="stage">
        <div className="canvas">
          {imgUrl ? (
            <div className="frame">
              <img src={imgUrl} alt="ad" />
              {pred && <HeatmapOverlay pred={pred} />}
              {pred && <TargetBox box={pred.target_box} />}
            </div>
          ) : (
            <div className="empty">Upload an ad to begin</div>
          )}
        </div>

        <aside className="panel">
          {score !== undefined && (
            <div className="score">
              <div className="num">{Math.round(score * 100)}%</div>
              <div className="lbl">attention on target</div>
              {agents && (
                <div className="delta">
                  {Math.round(agents.baseline_score * 100)}% → {Math.round(agents.final_score * 100)}%
                </div>
              )}
            </div>
          )}

          {pred?.distractors?.length ? (
            <div className="block">
              <h3>Attention thieves</h3>
              {pred.distractors.map((d, i) => (
                <div className="row" key={i}>
                  <span>{d.desc}</span>
                  <b>{Math.round(d.share * 100)}%</b>
                </div>
              ))}
            </div>
          ) : null}

          {agents && (
            <div className="block">
              <h3>Agent pipeline</h3>
              {agents.iterations.map((s, i) => (
                <div className="row" key={i}>
                  <span><b>{s.agent}</b> — {s.summary}</span>
                </div>
              ))}
              <p className="rationale">{agents.rationale}</p>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

// Heatmap: real data URL from backend, else a CSS-gradient stand-in so mock mode still looks alive.
function HeatmapOverlay({ pred }: { pred: PredictResult }) {
  if (pred.heatmap_png) {
    return <img className="heat" src={pred.heatmap_png} alt="heatmap" />;
  }
  const blobs = pred.distractors
    .map((d) => {
      const cx = (d.region[0] + d.region[2] / 2) * 100;
      const cy = (d.region[1] + d.region[3] / 2) * 100;
      return `radial-gradient(circle at ${cx}% ${cy}%, rgba(255,0,0,${0.15 + d.share}) 0%, rgba(255,0,0,0) 22%)`;
    })
    .join(",");
  return <div className="heat" style={{ backgroundImage: blobs }} />;
}

function TargetBox({ box }: { box: [number, number, number, number] }) {
  const [x, y, w, h] = box;
  return (
    <div
      className="target"
      style={{ left: `${x * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, height: `${h * 100}%` }}
    />
  );
}
