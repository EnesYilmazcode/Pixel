# Why most edits lost, and what wins now

October 2026. Every number here is measured with DeepGaze IIE on the local GPU, on the seven sample ads, unless it says otherwise.

## The bottleneck

There were three problems. Each one alone was enough to sink most edits.

**1. The edits added text, and text is the strongest thing DeepGaze looks at.** The old branch presets were "make several changes at once", "add a headline and call-to-action", "enlarge and brighten while gently dimming the surroundings", "remove clutter", and on top of every one the edit template said "you MAY add a bold call-to-action or wordmark" and "return a polished ad". So nearly every edit came back with a slogan or a button. I pasted one plain headline onto each original, outside the brand box. It cost 5 to 22 points on six of seven ads (Spotify -21.7, Pepsi -17.5, Coca-Cola -13.4). Put on the product itself, it still cost 4 to 6 points.

**2. Nano Banana redraws the whole frame.** Even for a one-object edit it shifts the picture by a few pixels and re-renders textures and colors everywhere. On the recorded preset edits, up to 94% of the frame outside the brand box changed structure. When I pasted back only the brand-box part of each recorded edit, the average change went from -11.8 points to -2.4, and 7 of 26 edits turned positive. Most of the damage happened outside the box.

**3. Several ads have almost no headroom.** The score is `r / (r + 1)`, where `r` is the attention inside the box divided by the box's share of the frame. Even if 100% of the attention lands in the box, the score can't go above `1 / (1 + box area)`.

| Ad | Score now | Best possible | Headroom |
|---|---|---|---|
| Nike | 59.2 | 88.1 | +28.9 |
| Red Bull | 79.0 | 88.5 | +9.5 |
| Spotify | 76.0 | 83.3 | +7.4 |
| Apple | 75.8 | 81.8 | +5.9 |
| Coca-Cola | 80.3 | 82.6 | +2.3 |
| McDonald's | 83.8 | 85.4 | +1.5 |
| Pepsi | 85.5 | 86.7 | +1.2 |

On Coca-Cola, McDonald's and Pepsi the brand already holds 86 to 90% of the attention, so the most any edit can gain is 1 to 2 points. Losing there is the honest answer, not a failure of the agents.

Smaller findings:
- **Making the product bigger doesn't help.** I scaled it 1.25x in place. With the box fixed, 5 of 7 ads lost (the product spills out of the box). With the box grown to match, all 7 lost 4 to 7 points. The size-invariant score is doing its job.
- **Moving the product toward the first fixation doesn't apply.** The first predicted fixation already lands in the brand box on 6 of 7 ads. Nike is the exception, and a billboard can't be moved.
- **A contrast and color pop on the product alone** gave +0.7 to +1.0 on four ads and nothing on the saturated ones. It's real, but too small to matter.
- **Cropping** helped only Nike (+17.3, by cutting the store signs out of the frame). It lost or did nothing on the other six, and it changes the brand box, so I left it out.
- **The Judge vetoes very little.** It gave the unedited originals 0.9 to 1.0, except Pepsi at 0.25, so it's noisy. It vetoed 2 of the 26 recorded preset edits I analyzed. It isn't the bottleneck.
- **The guard** rejected the old wins that dimmed the scene (see `backend/eval_guard.py`). That's correct, and it isn't why honest edits lost.

## What I tried

Four strategies on five ads (Nike, Red Bull, Spotify, Apple, Coca-Cola). Every edit used a template that forbids adding text and forbids touching anything else. They're scored against the old presets on the same five ads.

| Strategy | Beat the original | Mean change |
|---|---|---|
| Old presets (recorded runs, current guard) | 2 of 20 | -9.6 |
| Remove the named attention thief | 9 of 10 | +2.1 |
| Remove every prop in the scene | 1 of 5 | -0.2 |
| Group the props together, away from the product | 0 of 5 | -4.5 |
| Polish the product itself | 1 of 5 | -0.3 |

- **Grouping** was Enes's idea, and it failed for a mechanical reason: Nano Banana can't move things. Asked to gather the props in one corner, it pasted a shrunken copy of the hand and phone at the top of the frame, or added a "Modell's" sign.
- **Removing every prop** at once got the list from a Gemini inventory. That list included "water", "trees", "pants" and "background", and the model either did nothing or redrew the scene.
- **Best-of-N** (two candidates per branch, keep the higher score) looked attractive, but on Nike the higher-scoring candidate had replaced the bottom half of the billboard with a building. Picking by score alone rewards exactly that kind of damage, so I left it out.

## What ships

Branches remove the attention thieves one at a time, strongest first (`backend/branch_pool.py`):

1. DeepGaze finds the strongest attention peaks outside the brand box.
2. Gemini names each one from a crop, and says whether it belongs to the brand's own ad. The brand's own slogan or logo is never removed; an early run erased "Just do it." and called it a win.
3. Nano Banana removes that one thing, with no text and no other changes.
4. The edit is registered back onto the original. Only the pixels that really changed near the thief are pasted in (`backend/compose.py`), never the brand box. Everything else stays identical. A plain box around the thief cut objects in half, and a raw change mask left ghosts of removed objects, so each changed blob is pasted as a whole.
5. DeepGaze re-scores the result. The guard and Judge decide as before. A rise under half a point counts as noise, because re-rendering a region with no visible change moved the score that much.

If a branch wins, the next step works on the new image, and the next thief surfaces on its own.

Re-recorded demo runs (25 branches, 9 kept):

| Ad | Kept | Score |
|---|---|---|
| Nike | 4 of 5 | 59.2 to 77.0 |
| Red Bull | 2 of 5 | 79.0 to 81.0 |
| Spotify | 1 of 5 | 76.0 to 78.1 |
| Apple | 1 of 5 | 75.8 to 77.3 |
| Coca-Cola | 1 of 3 | 80.3 to 80.8 |
| McDonald's | 0 of 1 | no thieves, at its ceiling |
| Pepsi | 0 of 1 | no thieves, at its ceiling |

On Nike, the kept branches remove the Modell's/Subway storefront sign, a No Turns sign, the Swarovski logo and an A$AP Ferg poster, while the billboard and "Just do it." stay untouched. I checked every kept branch by eye.

## Limits

- Gemini's thief names are noisy ("white phone back" for a mouse, "blurred background" for an empty patch). A badly named thief usually produces no change, and the guard rejects it as imperceptible.
- Removing things helps most when there is clutter. A clean product shot is already near its ceiling, and no honest edit moves it much.
- Phase 2 used 80 image edits in all: 25 for the strategy experiments and 55 for building and re-recording the demo.
