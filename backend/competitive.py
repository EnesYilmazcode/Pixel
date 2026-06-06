"""Instance B — Scout: competitive analysis (the "dark horse" agent).

Two layers (see tasks/agent-layer-tasks.md):
  1. Memory: pinecone_seed.py builds the knowledge base (Pinecone + local kb.json).
  2. Per run: scout(brand, brief) retrieves the relevant rival tactics and
     synthesizes 3 concrete, applicable tactics for THIS ad.

Drop-in for agents.py: `scout(brand, brief)` returns {"tactics": [...]} — the same
shape the MVP stub returns, so wiring it in is a one-line import swap.

Degrades gracefully: Pinecone → local kb.json → built-in ADS. Gemini synthesis
if a key is present, else a clean templated synthesis. Always returns tactics.
"""
from __future__ import annotations

import json
from pathlib import Path

from config import settings

_KB = Path(__file__).with_name("data") / "competitors" / "kb.json"
_RUNS = Path(__file__).with_name("runs")

# Loose brand→family map so Scout pulls the right rival playbook. Unknown brands
# fall back to the full KB ranked by keyword overlap.
_FAMILY = {
    "coca-cola": "cola", "coke": "cola", "pepsi": "cola", "dr pepper": "cola",
    "nike": "apparel", "adidas": "apparel", "under armour": "apparel",
    "apple": "tech", "samsung": "tech", "google": "tech",
    "mcdonald's": "qsr", "mcdonalds": "qsr", "burger king": "qsr", "wendy's": "qsr",
    "spotify": "media", "netflix": "media",
    "liquid death": "beverage", "red bull": "beverage", "monster": "beverage",
}


def _text(v) -> str:
    """Flatten a str | list | None field to a plain string (Gemini briefs vary)."""
    if isinstance(v, list):
        return " ".join(str(x) for x in v)
    return str(v) if v else ""


def _load_kb() -> list[dict]:
    """Local fallback knowledge base (written by pinecone_seed.py). Empty if unseeded."""
    if _KB.exists():
        try:
            return json.loads(_KB.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Last resort: import the built-in list so Scout still works pre-seed.
    try:
        from pinecone_seed import ADS
        return ADS
    except Exception:
        return []


def _retrieve_local(brand: str, brief: dict, fam: str | None, k: int) -> list[dict]:
    """Family-first retrieval from the local KB, padded to k with the next-best rivals
    (excluding the brand itself) so Scout always has enough material for 3 tactics."""
    kb = [a for a in _load_kb() if a.get("brand", "").lower() != brand.lower()]
    # tone/dos may come back from Gemini as a string OR a list — flatten either to text.
    terms = (_text(brief.get("tone")) + " " + _text(brief.get("dos"))).lower().split()
    rank = lambda a: -sum(w in a.get("text", "").lower() for w in terms)
    same = sorted([a for a in kb if a.get("family") == fam], key=rank)
    rest = sorted([a for a in kb if a.get("family") != fam], key=rank)
    return (same + rest)[:k]


def _retrieve_pinecone(brand: str, brief: dict, fam: str | None, k: int) -> list[dict]:
    try:
        from google import genai
        from google.genai import types
        from pinecone import Pinecone
        gem = genai.Client(api_key=settings.gemini_api_key)
        q = f"{brand} {brief.get('tone', '')} ad layout attention CTA logo placement"
        vec = gem.models.embed_content(
            model=settings.gemini_embed_model, contents=q,
            config=types.EmbedContentConfig(output_dimensionality=settings.embed_dim),
        ).embeddings[0].values
        index = Pinecone(api_key=settings.pinecone_api_key).Index(settings.pinecone_index)
        res = index.query(vector=vec, top_k=k, namespace=fam or "", include_metadata=True)
        return [m["metadata"] for m in res.get("matches", [])]
    except Exception:
        return []


def _synthesize(brand: str, brief: dict, ads: list[dict]) -> list[dict]:
    """Turn retrieved rival ads into 3 tactics {tactic, evidence, apply}."""
    if settings.has_gemini:
        out = _synthesize_gemini(brand, brief, ads)
        if out:
            return out
    # Templated fallback: take the retrieved tactics directly (already actionable).
    seen, tactics = set(), []
    for a in ads:
        key = a.get("tactic")
        if key and key not in seen:
            seen.add(key)
            tactics.append({"tactic": a["tactic"],
                            "evidence": a.get("evidence", a.get("brand", "category leader")),
                            "apply": a.get("apply", "increase contrast on the brand target")})
        if len(tactics) >= 3:
            break
    return tactics or [{"tactic": "high-contrast focal target",
                        "evidence": "category leaders", "apply": "boost the product/CTA contrast and saturation"}]


def _synthesize_gemini(brand: str, brief: dict, ads: list[dict]) -> list[dict]:
    try:
        from google import genai
        gem = genai.Client(api_key=settings.gemini_api_key)
        corpus = "\n".join(f"- {a.get('brand')}: {a.get('text', a.get('tactic',''))}" for a in ads)
        prompt = (
            f"You are a creative strategist for {brand} (tone: {brief.get('tone')}). "
            f"From these competitor ad analyses:\n{corpus}\n\n"
            "Output ONLY a JSON array of exactly 3 objects "
            '{"tactic": short name, "evidence": which rival/why, '
            '"apply": one concrete image-edit instruction to raise attention on our brand target}. '
            f"Respect brand donts: {brief.get('donts', [])}."
        )
        txt = gem.models.generate_content(model=settings.gemini_text_model, contents=prompt).text
        s, e = txt.find("["), txt.rfind("]")
        arr = json.loads(txt[s:e + 1]) if s != -1 else []
        return [{"tactic": str(t["tactic"]), "evidence": str(t.get("evidence", "")),
                 "apply": str(t["apply"])} for t in arr][:3]
    except Exception:
        return []


def _write_brief(brand: str, tactics: list[dict], ads: list[dict]) -> None:
    """Debug + demo artifact: what Scout found this run."""
    try:
        _RUNS.mkdir(parents=True, exist_ok=True)
        lines = [f"# Scout brief — {brand}", "", "## Tactics"]
        for t in tactics:
            lines.append(f"- **{t['tactic']}** — {t['apply']}  _(via {t['evidence']})_")
        lines += ["", "## Retrieved rivals", *[f"- {a.get('brand')}: {a.get('tactic')}" for a in ads]]
        (_RUNS / f"scout_{brand.lower().replace(' ', '_')}.md").write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        pass  # artifacts are nice-to-have, never break the run


def scout(brand: str, brief: dict | None = None, k: int = 4) -> dict:
    """Scout agent entry point. Returns {"tactics": [ {tactic, evidence, apply} x3 ]}."""
    brief = brief or {}
    fam = _FAMILY.get(brand.strip().lower())

    ads, source = [], "local-kb"
    if settings.has_pinecone and settings.has_gemini:
        ads = _retrieve_pinecone(brand, brief, fam, k)
        if ads:
            source = "pinecone"
    if not ads:
        ads = _retrieve_local(brand, brief, fam, k)

    tactics = _synthesize(brand, brief, ads)
    _write_brief(brand, tactics, ads)
    return {"tactics": tactics, "source": source}


if __name__ == "__main__":
    # Smoke test (offline): seed first if needed, then run Scout.
    if not _KB.exists():
        import pinecone_seed
        pinecone_seed._write_local_artifacts()
    import json as _j
    print(_j.dumps(scout("Coca-Cola", {"tone": "bold, joyful", "dos": ["keep red dominant"],
                                        "donts": ["no Pepsi blue"]}), indent=2))
