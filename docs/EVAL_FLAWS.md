# Evaluation flaws & reward hacking

> An honest account of how Pixel scores an edit, where that score can be gamed, and
> what we do about it. The optimizer climbs a learned-saliency proxy, so this is a
> Goodhart's-law problem: *the moment a measure becomes a target, it stops being a good
> measure.* This doc states the failure modes plainly rather than hiding them.

## The core risk

The headline "attention score" is a **proxy** for human gaze produced by one saliency
model (DeepGaze IIE, with a CPU edge+center fallback when torch/weights are absent —
see `backend/deepgaze_runner.py`). Any optimizer that maximizes a proxy will, given
enough freedom, find inputs that score well *on the proxy* without improving the real
quantity. The Retoucher's branching search (`backend/agents.py` → `_make_scorer`,
`branch.search`) is exactly such an optimizer, and the per-step loop (`/optimize/step`
in `backend/main.py`) is a manual version of the same thing. The rest of this doc is
about narrowing that gap.

## How the eval works now

- **Size-invariant prominence, not raw mass.** `deepgaze_runner.prominence(density, box)`
  computes `ratio = (attention mass in the box) / (box's area fraction)` then
  `score = ratio / (ratio + 1)`. So **0.5 = the region is exactly average salience for
  its size**, >0.5 = it out-pulls its size, <0.5 = it under-pulls. The earlier metric was
  raw mass-in-box (`attention_in_box`), which rewards simply *enlarging* the target. The
  prominence index removes that lever, so the search is pushed toward composition /
  contrast / de-clutter rather than "make the logo bigger." (The raw mass is still
  computed and exposed as `target_salience` — but as a guard input, not the headline.)
- **Flat (content-driven) centerbias.** `deepgaze_runner._centerbias` returns a uniform
  log-density. DeepGaze requires a centerbias input; a center prior would mask exactly
  the changes we care about (de-cluttering or suppressing an off-center distractor barely
  moves the number under a strong prior) and would unfairly penalize off-center targets.
  Flat = the score reflects where the *content* draws the eye.
- **A reward-hack guard.** `backend/eval_guard.py` (`verdict(...)`) is a cheap second
  opinion run on every accepted edit. It checks: (1) **perceptibility** — windowed +
  global SSIM; an invisible/sub-JND tweak is rejected as a likely adversarial hack;
  (2) **suppression** — if the target's *share* rose but its **absolute** salience
  (`target_salience`) did not, the edit won by blurring/stripping the rest of the frame,
  and is rejected; (3) **global change without confirmation** — an edit covering most of
  the frame with no absolute-salience gain is sent to `review`, not silently accepted;
  (4) optional **two-model agreement** when a second saliency signal is supplied.
- **Honest before/after.** `/optimize/step` reports the **real** `delta` (it can be
  negative) and gates `improved` on `new_score > current AND not vetoed AND guard
  accepted`. `agents.run()` keeps the best variant it actually found, reports its real
  delta, and leaves failed attempts visible in the returned `tree`; if nothing beats the
  original it keeps the original at delta 0. The lift is never fabricated.
- **Honest `/health`.** `deepgaze_runner.model_loaded()/engine_name()/device_name()` drive
  `/health`, which reports `mode: live|degraded`, `deepgaze_loaded`, `engine`, and
  `device`. The fallback engine can never silently pose as the real model; the frontend
  shows a LIVE/DEMO badge from this.

## Reward-hack risks that remain (and how we mitigate each)

- **Single model, single metric.** We optimize one DeepGaze instance against one scalar.
  An edit can exploit that specific network. *Mitigation:* the guard supports a second
  saliency signal (`sal2_before/after`) and flags disagreement as `review`; today that
  input is usually absent, so this is partial.
- **OOD scoring of AI-generated images.** Gemini ("Nano Banana") edits produce textures
  and artifacts unlike the natural-image distribution DeepGaze was trained on, so the
  score is least trustworthy exactly where the optimizer spends most of its time.
  *Mitigation:* the brand-fit Judge gate (`agents._make_scorer`) penalizes garish/off-brand
  variants, and the guard's perceptibility check catches degenerate textures — but neither
  fully closes the OOD gap.
- **Low-level feature pumps.** Saliency models react to local contrast/edges, so a high-
  frequency border or a hard vignette can inflate prominence without real design merit.
  *Mitigation:* the Judge gate scales down off-brand/garish edits so they can't win on raw
  attention; the prominence metric (not raw mass) also reduces the payoff of crude pumps.
- **Win by suppression.** The classic cheat — raise the target's *share* by darkening/
  blurring everything else. *Mitigation:* this is the guard's primary job: `verdict`
  rejects an edit whose `ratio` rose while `target_salience` stayed flat or fell.
- **Box drift mid-optimization.** If the target box is re-detected after each edit, the
  optimizer can "win" by relocating the box to wherever attention already pools.
  *Mitigation (structural, partly TODO):* freeze the target box at round 0 and re-score the
  same region — the per-step loop already threads a fixed `tbox` through; the full search
  should do the same explicitly.

## What to change next (ranked)

1. **Second saliency model, required agreement.** Wire a genuinely different model (or a
   non-DeepGaze classical map) into `sal2_*` and require directional agreement before
   `accept`. This is the single biggest hardening.
2. **Freeze the target box at round 0 everywhere.** Make box-freezing an explicit
   invariant in `agents._step_optimize`, not just the per-step path.
3. **Calibrate the guard thresholds** (`SSIM_FLOOR`, `DIFF_THRESH`, `GLOBAL_*` in
   `eval_guard.py`) on a labelled set of obviously-visible vs invisible edits — they are
   currently approximate.
4. **Report a confidence band, not a point estimate** — e.g. score under small
   augmentations (crop/jitter) so a brittle, augmentation-sensitive "win" is visible.
5. **Hold-out human or eye-tracking spot-check** on a few hero ads to anchor the proxy to
   ground truth at least once.

## Honest caveats

- The score is a **prominence index, not a percentage of human attention.** 0.5 means
  "average for its size," not "50% of viewers looked here."
- DeepGaze IIE predicts *free-viewing* saliency; it does not model task, brand
  familiarity, or motion, and it is least reliable on AI-generated imagery.
- The guard reduces, but does not eliminate, reward hacking — it is a set of cheap
  heuristics with approximate thresholds, not a proof of honesty.
- A `review` verdict means "we couldn't confirm this is real," not "this is fine." Treat
  flagged wins as unconfirmed.
