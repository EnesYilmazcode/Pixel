"""Instance B — seed the competitive-ad memory (Scout's knowledge base).

Run once:  python pinecone_seed.py

- With PINECONE_API_KEY + GEMINI_API_KEY: embeds each ad analysis and upserts to
  the `pixel-ads` index (namespace per brand family).
- Always (even with no keys): writes human-readable `data/competitors/<brand>.md`
  per brand AND a local `data/competitors/kb.json` fallback so Scout is fully
  data-driven offline (demo-safe). Pinecone is an upgrade, not a hard dependency.

The `.md` files double as the "write findings to files so we understand them"
artifact + a demo prop (open one on stage to show the research).
"""
from __future__ import annotations

import json
from pathlib import Path

from config import settings

_DATA = Path(__file__).with_name("data") / "competitors"

# Curated competitive-ad analyses. `family` groups rivals so Scout can pull the
# right playbook for an uploaded ad. Keep these concrete + tactic-bearing.
ADS: list[dict] = [
    {"brand": "Pepsi", "family": "cola", "year": 2023,
     "tactic": "high-contrast CTA", "apply": "boost the can/CTA saturation and edge contrast vs background",
     "evidence": "Pepsi 2023 'Thirsty' run",
     "text": "Pepsi cola ad: single hero can, deep blue field, white logo at high contrast; "
             "minimal background clutter keeps fixation on the product and tagline."},
    {"brand": "Coca-Cola", "family": "cola", "year": 2022,
     "tactic": "warm focal lighting", "apply": "add a soft warm highlight behind the product to lift it off the scene",
     "evidence": "Coca-Cola holiday 2022",
     "text": "Coca-Cola ad: red-dominant frame, condensation on a backlit bottle; warm rim light "
             "draws the eye to the bottle silhouette and the script logo."},
    {"brand": "Dr Pepper", "family": "cola", "year": 2023,
     "tactic": "bold center logo lockup", "apply": "anchor the logo near the optical center, large and unobstructed",
     "evidence": "Dr Pepper 2023",
     "text": "Dr Pepper ad: maroon palette, oversized centered logo, faces kept to the periphery so "
             "they don't steal gaze from the brand mark."},
    {"brand": "Nike", "family": "apparel", "year": 2023,
     "tactic": "negative space around the mark", "apply": "clear visual clutter around the logo so it owns its space",
     "evidence": "Nike 'Just Do It' 2023",
     "text": "Nike ad: stark negative space, single athlete, swoosh in the lower third with nothing competing; "
             "eye lands on athlete then swoosh."},
    {"brand": "Adidas", "family": "apparel", "year": 2022,
     "tactic": "diagonal lead-in lines", "apply": "use diagonal composition lines that point toward the product/logo",
     "evidence": "Adidas 2022",
     "text": "Adidas ad: diagonal track lines guide the gaze from the model's stride down to the three-stripe mark."},
    {"brand": "Apple", "family": "tech", "year": 2023,
     "tactic": "product-on-seamless", "apply": "isolate the product on a clean seamless background, kill distractors",
     "evidence": "Apple iPhone 2023",
     "text": "Apple ad: product floats on seamless gradient, no human faces, specular highlights define the device; "
             "attention is almost entirely on the product."},
    {"brand": "Samsung", "family": "tech", "year": 2022,
     "tactic": "screen-as-hero", "apply": "make the screen content the brightest, highest-contrast region",
     "evidence": "Samsung Galaxy 2022",
     "text": "Samsung ad: the lit display is the brightest patch in frame, pulling fixation to the screen and logo beneath."},
    {"brand": "McDonald's", "family": "qsr", "year": 2023,
     "tactic": "appetite-color pop", "apply": "saturate the food/product so warm tones dominate the gaze",
     "evidence": "McDonald's 2023",
     "text": "McDonald's ad: warm reds/yellows, the product hyper-saturated against a muted ground; the food is the focal point."},
    {"brand": "Burger King", "family": "qsr", "year": 2022,
     "tactic": "flame/texture detail", "apply": "add crisp product texture detail to reward and hold fixation",
     "evidence": "Burger King 2022",
     "text": "Burger King ad: macro flame-grill texture on the patty; high-frequency detail holds the eye on the product."},
    {"brand": "Spotify", "family": "media", "year": 2023,
     "tactic": "duotone subject + bright CTA", "apply": "duotone the scene so a single bright CTA wins attention",
     "evidence": "Spotify Wrapped 2023",
     "text": "Spotify ad: bold duotone imagery, one vivid green CTA that is the only saturated element, so it owns the gaze."},
    {"brand": "Liquid Death", "family": "beverage", "year": 2023,
     "tactic": "irreverent contrast can", "apply": "keep the can high-contrast and central; lean edgy minimalism",
     "evidence": "Liquid Death 2023",
     "text": "Liquid Death ad: stark black/white, the tallboy can centered and high-contrast; minimal scene so the can dominates."},
    {"brand": "Red Bull", "family": "beverage", "year": 2022,
     "tactic": "action vector to logo", "apply": "orient action/motion so it visually points at the can and logo",
     "evidence": "Red Bull 2022",
     "text": "Red Bull ad: athlete mid-air, motion vector resolves toward the can; logo placed at the motion endpoint."},
]


def _write_local_artifacts() -> None:
    """Always-available outputs: per-brand .md + kb.json (offline Scout fallback)."""
    _DATA.mkdir(parents=True, exist_ok=True)
    by_brand: dict[str, list[dict]] = {}
    for ad in ADS:
        by_brand.setdefault(ad["brand"], []).append(ad)
    for brand, ads in by_brand.items():
        lines = [f"# Competitive analysis — {brand}", ""]
        for ad in ads:
            lines += [f"## {ad['tactic']} ({ad['year']})",
                      f"- **Apply:** {ad['apply']}",
                      f"- **Evidence:** {ad['evidence']}",
                      f"- {ad['text']}", ""]
        (_DATA / f"{brand.lower().replace(' ', '_')}.md").write_text("\n".join(lines), encoding="utf-8")
    (_DATA / "kb.json").write_text(json.dumps(ADS, indent=2), encoding="utf-8")
    print(f"Wrote {len(by_brand)} brand briefs + kb.json to {_DATA}")


def _seed_pinecone() -> None:
    """Embed + upsert to Pinecone. No-op (with a notice) if keys/SDK missing."""
    if not (settings.has_pinecone and settings.has_gemini):
        print("Pinecone/Gemini keys absent — skipped vector upsert (local kb.json still works).")
        return
    try:
        from google import genai
        from pinecone import Pinecone
    except ImportError:
        print("pinecone / google-genai not installed — uncomment them in requirements.txt. "
              "Local kb.json still works.")
        return

    gem = genai.Client(api_key=settings.gemini_api_key)
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(settings.pinecone_index)
    for i, ad in enumerate(ADS):
        emb = gem.models.embed_content(model="text-embedding-004", contents=ad["text"])
        vec = emb.embeddings[0].values
        index.upsert(
            namespace=ad["family"],
            vectors=[{"id": f"ad-{i}", "values": vec,
                      "metadata": {k: ad[k] for k in ("brand", "family", "year", "tactic", "apply", "evidence", "text")}}],
        )
    print(f"Upserted {len(ADS)} ads to Pinecone index '{settings.pinecone_index}'.")


if __name__ == "__main__":
    _write_local_artifacts()
    _seed_pinecone()
