// API client + types. Matches the frozen contract in WORK_ALLOCATION.md.
// Per-endpoint mock flags: /predict is live (real DeepGaze backend), /agents is
// mocked until the competitive.py:55 brief["tone"] list/str bug is fixed (it 500s).
import mock from "./mock.json";

export const USE_MOCK_PREDICT = false; // real DeepGaze via Vite proxy → :8000
export const USE_MOCK_AGENTS = true;   // TODO: flip once /agents stops 500ing
export const USE_MOCK = USE_MOCK_PREDICT && USE_MOCK_AGENTS;
export const MODE_LABEL = USE_MOCK_PREDICT ? "Mock data" : "Live gaze · mock optimize";

export type Box = [number, number, number, number]; // normalized x,y,w,h
export type Distractor = { region: Box; share: number; desc: string };
export type Fixation = { x: number; y: number; order: number };

export type PredictResult = {
  width: number;
  height: number;
  attention_score: number;
  heatmap_png: string; // data URL ("" in mock -> CSS fallback overlay)
  target_box: Box;
  scanpath: Fixation[];
  distractors: Distractor[];
};

export type EditResult = {
  variant_png: string;
  edit_description: string;
  width: number;
  height: number;
};

export type AgentStep = { agent: string; status: string; summary?: string };
export type TreeNode = {
  id: number;
  parent: number | null;
  depth: number;
  score: number;
  status: "root" | "alive" | "dead" | "pruned" | "best";
  directive: string;
};
export type AgentsResult = {
  tree?: TreeNode[];
  baseline_score: number;
  final_score: number;
  delta: number;
  brand_brief?: Record<string, unknown>;
  competitive_insights?: { tactics: unknown[] };
  heatmap_before: string;
  heatmap_after: string;
  variant_png: string;
  rationale: string;
  iterations: AgentStep[];
};

export async function predict(file: File, target?: Box): Promise<PredictResult> {
  if (USE_MOCK_PREDICT) return mock.predict as PredictResult;
  const fd = new FormData();
  fd.append("image", file);
  if (target) fd.append("target", JSON.stringify(target)); // score against the brand's region
  const r = await fetch("/predict", { method: "POST", body: fd });
  if (!r.ok) throw new Error(`/predict ${r.status}`);
  return r.json();
}

export async function runAgents(file: File, brand: string): Promise<AgentsResult> {
  if (USE_MOCK_AGENTS) return mock.agents as AgentsResult;
  const fd = new FormData();
  fd.append("image", file);
  fd.append("brand", brand);
  const r = await fetch("/agents", { method: "POST", body: fd });
  if (!r.ok) throw new Error(`/agents ${r.status}`);
  return r.json();
}
