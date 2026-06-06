import { useEffect, useState } from "react";

// Looping landing illustration of the optimize loop: an ad splits into variant edits,
// weak branches die, strong ones survive and grow, until a best emerges — then it loops.
// Decorative (synthetic scores) — it shows HOW Pixel works, not a specific run.
const BASE = 28;
const ROUNDS: { score: number; keep: boolean }[][] = [
  [{ score: 41, keep: true }, { score: 33, keep: false }, { score: 37, keep: false }],
  [{ score: 54, keep: true }, { score: 47, keep: false }, { score: 44, keep: false }],
  [{ score: 67, keep: true }, { score: 58, keep: false }, { score: 61, keep: false }],
];
const STEPS = 1 + ROUNDS.length * 2 + 1; // root, then per round (spawn, prune), then hold

export default function HeroBranches() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep((s) => (s + 1) % (STEPS + 1)), 950);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="hb" aria-hidden="true">
      <div className="hb-flow">
        {/* the original ad */}
        <div className="hb-col">
          <div className="hb-cap">your ad</div>
          <div className={`hb-tile root ${step >= 0 ? "in working" : ""}`}>
            <span className="hb-pct">{BASE}%</span>
            <span className="hb-tag">attention</span>
          </div>
        </div>

        {ROUNDS.map((variants, r) => {
          const spawned = step >= 1 + r * 2;
          const pruned = step >= 2 + r * 2;
          return (
            <div className="hb-col" key={r}>
              <div className={`hb-cap ${spawned ? "in" : ""}`}>round {r + 1}</div>
              {variants.map((v, i) => {
                const state = !spawned ? "hidden" : !pruned ? "working" : v.keep ? "best" : "dead";
                return (
                  <div className={`hb-tile in ${state}`} key={i} style={{ transitionDelay: `${i * 70}ms` }}>
                    <span className="hb-pct">{v.score}%</span>
                    <span className="hb-tag">{!pruned ? "testing" : v.keep ? "kept" : "pruned"}</span>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
      <div className="hb-foot">
        <span className="hb-dot" /> agents redirect attention, branch by branch
      </div>
    </div>
  );
}
