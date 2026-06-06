"""Campaign persistence — one JSON file per campaign under backend/campaigns/.

A campaign = the uploaded ad (as a data URL) + an ordered list of optimization runs
(each run is a full /agents result, so resuming shows exactly where you left off).
Filesystem + JSON is plenty for a hackathon; swap for a DB later if needed.
The campaigns/ dir is git-ignored (user data).
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

_ROOT = Path(__file__).with_name("campaigns")


def _file(cid: str) -> Path:
    return _ROOT / cid / "campaign.json"


def _write(rec: dict) -> None:
    f = _file(rec["id"])
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(rec), encoding="utf-8")


def create_campaign(name: str, brand: str, original_png: str) -> dict:
    """Start a campaign from an uploaded image (PNG data URL)."""
    rec = {
        "id": uuid.uuid4().hex[:8],
        "name": name or "Untitled campaign",
        "brand": brand or "the brand",
        "created_at": time.time(),
        "original_png": original_png,
        "runs": [],
    }
    _write(rec)
    return rec


def get_campaign(cid: str) -> dict:
    """Full record (original image + all runs) — used to resume. Raises if missing."""
    return json.loads(_file(cid).read_text(encoding="utf-8"))


def save_run(cid: str, result: dict) -> dict:
    """Append an optimization run (a full /agents result) and return the campaign."""
    rec = get_campaign(cid)
    rec["runs"].append({
        "n": len(rec["runs"]) + 1,
        "at": time.time(),
        "baseline_score": result.get("baseline_score"),
        "final_score": result.get("final_score"),
        "delta": result.get("delta"),
        "result": result,
    })
    _write(rec)
    return rec


def list_campaigns() -> list[dict]:
    """Lightweight gallery list (newest first): meta + a thumbnail, no full run data."""
    out = []
    if _ROOT.exists():
        for d in _ROOT.iterdir():
            f = d / "campaign.json"
            if not f.exists():
                continue
            r = json.loads(f.read_text(encoding="utf-8"))
            latest = r["runs"][-1] if r["runs"] else None
            out.append({
                "id": r["id"], "name": r["name"], "brand": r["brand"],
                "created_at": r["created_at"], "runs": len(r["runs"]),
                "latest_score": latest["final_score"] if latest else None,
                "thumbnail": r.get("original_png", ""),
            })
    return sorted(out, key=lambda c: c["created_at"], reverse=True)
