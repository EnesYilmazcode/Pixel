"""The branch edits Pixel tries on an ad. Plain data, no model calls, so it is easy to test."""
from __future__ import annotations


def branches(before: dict, brand: str) -> list[dict]:
    """Branch edits for one image, strongest first. Each is {"directive", "region"}:
    one concrete change, and the normalized boxes the edit is allowed to touch (see
    compose.keep_region).

    Every branch removes one attention thief, the strongest first, because that is the
    edit the measurements back: on five ads, removing the named thief beat the original
    in 9 of 10 tries (mean +2.1 points), while the old presets (headline, CTA, several
    changes at once, dimming the surroundings) won 2 of 20 (mean -9.6). See
    docs/PIXEL_FINDINGS.md. Last comes a small polish of the product itself, which rarely
    wins but is the only honest move left on an ad with no thieves. No branch adds text
    or dims the scene."""
    out = []
    for d in before.get("distractors", []):
        what = d["desc"]
        if what.endswith(" region"):  # unnamed: Gemini couldn't label it
            what = f"distracting object in the {what} of the photo"
        out.append({
            "directive": f"remove the {what} completely and fill its area with what would "
                         f"naturally be behind it",
            "region": [d["region"]],
        })
    out.append({
        "directive": f"make the {brand} product itself a little crisper and cleaner: sharper "
                     f"label and logo edges and clean highlights, same color, same size, same place",
        "region": [before["target_box"]],
    })
    return out
