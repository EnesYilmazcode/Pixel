import { useEffect, useState } from "react";
import type { TreeNode } from "./api";

// The interactive optimization workspace: the original ad broken into branch-search
// variants. Click any node to load its image + the exact Nano Banana prompt that made
// it, with its attention score and lift vs the original. Self-contained (own state) so
// it composes cleanly into App without extra wiring.
export default function BranchWorkspace({ tree, baseline }: { tree: TreeNode[]; baseline: number }) {
  const root = tree.find((n) => n.parent === null) ?? tree[0];
  const best = tree.reduce((a, b) => (b.score > a.score ? b : a), root);
  const [sel, setSel] = useState<number>(best.id);
  useEffect(() => setSel(best.id), [best.id]);

  const node = tree.find((n) => n.id === sel) ?? best;
  const depths = Array.from(new Set(tree.map((n) => n.depth))).sort((a, b) => a - b);
  const isOriginal = node.parent === null;
  const delta = Math.round((node.score - baseline) * 100);
  const kept = node.id === best.id && best.id !== root.id;

  return (
    <section className="workspace">
      <div className="ws-head">
        <h3>Optimization workspace</h3>
        <span className="ws-hint">click any branch to see its edit ↓</span>
      </div>

      <div className="ws-body">
        <div className="ws-preview">
          <div className="frame">
            {node.image ? (
              <>
                <img className="base" src={node.image} alt="selected variant" />
                {node.heatmap && <img className="heat" src={node.heatmap} alt="attention" />}
              </>
            ) : (
              <div className="ws-noimg">
                <span>Pruned variant</span>
                <small>scored below the field — dropped, so no preview was kept</small>
              </div>
            )}
            <span className={`frame-badge ${isOriginal ? "orig" : kept ? "" : "dead"}`}>
              {isOriginal ? "original" : kept ? "✦ winner" : "pruned"}
            </span>
          </div>
        </div>

        <div className="ws-detail">
          <div className="ws-score">
            <span className="ws-pct">{Math.round(node.score * 100)}<i>%</i></span>
            <span className="ws-lbl">attention on target</span>
            {!isOriginal && (
              <span className={`ws-delta ${delta >= 0 ? "up" : "down"}`}>
                {delta >= 0 ? "+" : ""}{delta} pts vs original
              </span>
            )}
          </div>
          <div className="ws-prompt">
            <div className="ws-prompt-h">{isOriginal ? "Original creative" : "Nano Banana edit prompt"}</div>
            <p className="ws-prompt-body">
              {isOriginal ? "The uploaded ad — baseline attention before any edit." : `"${node.directive}"`}
            </p>
            {!isOriginal && (
              <div className={`ws-verdict ${kept ? "kept" : "pruned"}`}>
                {kept ? "✓ kept — best score this round" : "✕ pruned — didn't beat the original"}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="ws-tree">
        {depths.map((d) => (
          <div className="ws-col" key={d}>
            <div className="ws-col-h">{d === 0 ? "original" : `round ${d} · ${tree.filter((n) => n.depth === d).length} edits`}</div>
            <div className="ws-col-nodes">
              {tree
                .filter((n) => n.depth === d)
                .sort((a, b) => b.score - a.score)
                .map((n, i) => {
                  const win = n.id === best.id && best.id !== root.id;
                  const dead = n.parent !== null && !win;
                  const cls = n.parent === null ? "root" : win ? "best" : "dead";
                  return (
                    <button
                      key={n.id}
                      className={`ws-node ${cls} ${n.id === sel ? "sel" : ""}`}
                      onClick={() => setSel(n.id)}
                      style={{ animationDelay: `${d * 0.35 + i * 0.12}s` }}
                      title={n.directive}
                    >
                      {n.image ? <img src={n.image} alt="" /> : <span className="ws-node-noimg">pruned edit</span>}
                      <span className="ws-node-bar">
                        <span className="ws-node-score">{Math.round(n.score * 100)}%</span>
                        {n.parent !== null && <span className="ws-node-tag">{win ? "kept" : dead ? "pruned" : ""}</span>}
                      </span>
                    </button>
                  );
                })}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
