import { useEffect, useState } from "react";

// Skeleton-loader-style illustration of the search: one box splits into branches,
// weak ones gray out, a path survives and splits again, until a winner is highlighted.
// No numbers or labels — just the gist. Loops.
type Node = { id: string; x: number; y: number; parent?: string; appear: number; die?: number; win?: boolean };

const NODES: Node[] = [
  { id: "r", x: 50, y: 11, appear: 0 },
  { id: "a", x: 19, y: 46, parent: "r", appear: 1, die: 2 },
  { id: "b", x: 50, y: 46, parent: "r", appear: 1 },
  { id: "c", x: 81, y: 46, parent: "r", appear: 1, die: 2 },
  { id: "d", x: 35, y: 84, parent: "b", appear: 2, die: 3 },
  { id: "w", x: 66, y: 84, parent: "b", appear: 3, win: true },
];

export default function HeroBranches() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep((s) => (s + 1) % 6), 820); // ...3=winner, 4-5=hold, loop
    return () => clearInterval(id);
  }, []);

  const find = (id?: string) => NODES.find((n) => n.id === id);
  const stateOf = (n: Node) =>
    step < n.appear ? "hidden"
    : n.die != null && step >= n.die ? "dead"
    : n.win ? "win"
    : "alive";

  return (
    <div className="hb" aria-hidden="true">
      <svg className="hb-edges" viewBox="0 0 100 100" preserveAspectRatio="none">
        {NODES.filter((n) => n.parent).map((n) => {
          const p = find(n.parent)!;
          const st = stateOf(n);
          return (
            <line
              key={n.id}
              x1={p.x} y1={p.y + 6} x2={n.x} y2={n.y - 6}
              className={`hb-edge ${st === "hidden" ? "off" : st === "dead" ? "dead" : ""}`}
            />
          );
        })}
      </svg>
      {NODES.map((n) => (
        <div key={n.id} className={`hb-node ${stateOf(n)}`} style={{ left: `${n.x}%`, top: `${n.y}%` }}>
          <i /><i />
        </div>
      ))}
    </div>
  );
}
