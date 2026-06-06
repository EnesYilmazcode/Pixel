# frontend/CLAUDE.md — Design

Vite + React + TS. Dark, minimalist, demo-first. **Less chrome, more signal.**

## Principles
- **Minimalist.** One primary action per view. Cut anything that isn't the heatmap, the score, or the lift.
- **Let the work be the UI.** The ad image, the heatmap overlay, and the rising number are the hero — frame them, don't decorate them.
- **Calm by default, loud on the payoff.** Neutral surfaces; reserve `--accent`/`--good` for the score and the before→after delta.
- **No new dependencies** for styling. Plain CSS in `index.css`, reuse the vars below. No UI kits, no icon libs.

## Tokens (defined in `index.css` — never hardcode hex)
`--bg #0e0f13` · `--panel #16181f` · `--line #262a35` · `--txt #e7e9ee` · `--muted #9aa0ad` · `--accent #ff3b30` (CTA / brand) · `--good #34d399` (score lift)

## Conventions
- Radius `8–12px`, `1px solid var(--line)` borders, generous gap (`12–24px`). No shadows, no gradients (except the heatmap stand-in).
- System font stack only. Sizes already scale in `index.css`; match what's there.
- States are explicit and quiet: `disabled` → 0.4 opacity; busy → muted text, not spinners.
- Components live in their own file once they outgrow a helper. Keep `App.tsx` to layout + state.
- Build against `mock.json`; never block on the backend.

## Don't
Add libraries, gradients, animations beyond the score counter, or copy that explains what a button obviously does.
