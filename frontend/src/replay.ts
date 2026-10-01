// Replay mode for the static web demo (vite build --mode demo). There is no backend, so the
// API calls are answered from runs recorded against the real one by scripts/record_demo.py:
// the DeepGaze heatmaps, scores, Nano Banana edits, Judge and guard verdicts are all real.
// Only the waiting is staged, so a run still reads as a run.
import type { Health, PredictResult, StepResult } from "./api";

const BASE = import.meta.env.BASE_URL;
const url = (p: string) => BASE + p;
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

const json = new Map<string, Promise<unknown>>();
function getJson<T>(path: string): Promise<T> {
  if (!json.has(path)) {
    json.set(path, fetch(url(path)).then((r) => {
      if (!r.ok) throw new Error(`${path} ${r.status}`);
      return r.json();
    }));
  }
  return json.get(path) as Promise<T>;
}

// Start fetching an image now so it is decoded by the time the result is shown.
function preload(src: string): Promise<void> {
  const img = new Image();
  img.src = src;
  return img.decode().catch(() => undefined);
}

export const health = async (): Promise<Health> => ({
  ok: true, mode: "replay", deepgaze_loaded: true, engine: "deepgaze-iie",
  device: "cuda", gemini: true, pinecone: false,
});

export async function predict(sample: string): Promise<PredictResult> {
  const [p] = await Promise.all([getJson<PredictResult>(`replay/${sample}/predict.json`), wait(700)]);
  const heat = url(p.heatmap_png);
  await preload(heat);
  return { ...p, heatmap_png: heat };
}

export async function optimizeStep(sample: string, step: number): Promise<StepResult> {
  const steps = await getJson<StepResult[]>(`replay/${sample}/steps.json`);
  const s = steps[step];
  if (!s) throw new Error(`No recorded branch ${step + 1} for this ad`);
  const variant = url(s.variant_png);
  const heat = s.variant_heatmap ? url(s.variant_heatmap) : undefined;
  await Promise.all([preload(variant), heat && preload(heat), wait(1800)]);
  return { ...s, variant_png: variant, variant_heatmap: heat, n_directives: steps.length };
}

// Small gallery thumbnail, so the phone doesn't pull eight full-size photos up front.
export const thumb = (sample: string) => url(`replay/${sample}/thumb.jpg`);
