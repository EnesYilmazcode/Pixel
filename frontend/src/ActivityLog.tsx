import { useEffect, useState } from "react";
import type { PredictResult, AgentsResult } from "./api";

// Live activity feed. Reveals the REAL pipeline (pred + agents.iterations) step by
// step on a timer, so the run reads as a live process instead of an instant jump.
// The data is real; only the pacing is presentational.
const VERB: Record<string, string> = {
  Insider: "reading the brand",
  Scout: "searching rival campaigns",
  Eye: "scoring attention with DeepGaze",
  Retoucher: "generating variant edits",
  Critic: "checking brand-fit",
  Judge: "judging variants",
};

type Props = { busy: string; pred: PredictResult | null; agents: AgentsResult | null };

function Line({ label, detail, state, good }: { label: string; detail?: string; state: "run" | "done"; good?: boolean }) {
  return (
    <div className={`logline ${state} ${good ? "good" : ""}`}>
      <span className="logdot" />
      <span className="logtxt">
        <b>{label}</b>{detail ? <> · {detail}</> : null}
      </span>
    </div>
  );
}

export default function ActivityLog({ busy, pred, agents }: Props) {
  const steps = agents?.iterations ?? [];
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (!agents) { setShown(0); return; }
    setShown(0);
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setShown(i);
      if (i >= steps.length) clearInterval(id);
    }, 720);
    return () => clearInterval(id);
  }, [agents]); // eslint-disable-line react-hooks/exhaustive-deps

  const analyzing = busy.startsWith("Analyzing") || busy.startsWith("Loading");
  const optimizing = busy.startsWith("Agents") && !agents;
  const pct = (n: number) => Math.round(n * 100);

  return (
    <div className="block log">
      <h3>Live activity</h3>
      <div className="loglines">
        {analyzing && <Line state="run" label="DeepGaze" detail="predicting attention…" />}

        {pred && (
          <>
            <Line state="done" label="Ingested" detail="campaign image" />
            <Line state="done" label="DeepGaze" detail={`baseline ${pct(pred.attention_score)}% on target`} />
            {pred.distractors?.[0] && (
              <Line state="done" label="Eye" detail={`thief: ${pred.distractors[0].desc} (${pct(pred.distractors[0].share)}%)`} />
            )}
          </>
        )}

        {optimizing && <Line state="run" label="Agents" detail="spinning up the team…" />}

        {steps.map((s, i) =>
          i < shown ? (
            <Line key={i} state="done" label={s.agent} detail={s.summary} />
          ) : i === shown ? (
            <Line key={i} state="run" label={s.agent} detail={`${VERB[s.agent] ?? "working"}…`} />
          ) : null
        )}

        {agents && shown >= steps.length && (
          <Line state="done" good label="Result"
            detail={`${pct(agents.baseline_score)}% → ${pct(agents.final_score)}% (+${pct(agents.delta)} pts)`} />
        )}
      </div>
    </div>
  );
}
