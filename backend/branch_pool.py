"""The branch edits Pixel tries on an ad. Plain data, no model calls, so it is easy to test."""
from __future__ import annotations


def branches(before: dict, brand: str) -> list[dict]:
    """Branch edits for one image, strongest first. Each is {"directive", "region",
    "protect"}: one concrete change, the normalized boxes the change must stay near, and
    the boxes it must never touch (see compose.keep_changes).

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
                         f"naturally be behind it. Keep the {brand} ad, product, logo and slogan "
                         f"exactly as they are",
            "region": [d["region"]],
            "protect": [before["target_box"]],
        })
    # Asked for a crisper "label", the model wrote a new one, so this names no text at all.
    out.append({
        "directive": f"make the surface of the {brand} product a little crisper and cleaner with "
                     f"clean highlights, without adding, changing or removing any text or logo",
        "region": [before["target_box"]],
        "protect": [],
    })
    return out
