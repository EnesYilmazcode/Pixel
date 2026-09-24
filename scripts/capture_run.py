"""Run the real optimizer on one sample ad and keep every edit it tried.

    python scripts/capture_run.py the-ordinary "The Ordinary"

Needs GEMINI_API_KEY and the backend deps. Writes results/<sample>/edit<k>.jpg for each
Nano Banana edit and results/<sample>/run.json with each edit's directive, its
size-invariant prominence and absolute on-target salience, and the search tree.
make_showcase.py draws assets/media/every-edit.png from this folder.
"""
from __future__ import annotations

import json
import re
import sys
import threading
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import agents  # noqa: E402
import deepgaze_runner as dg  # noqa: E402
import gemini  # noqa: E402


def target_box(sample: str) -> list[float]:
    src = (ROOT / "frontend" / "src" / "samples.ts").read_text(encoding="utf-8")
    m = re.search(r'id: "{}".*?target_box: \[([^\]]+)\]'.format(re.escape(sample)), src, re.S)
    return [float(v) for v in m.group(1).split(",")]


def main():
    sample, brand = sys.argv[1], sys.argv[2]
    box = target_box(sample)
    out = ROOT / "results" / sample
    out.mkdir(parents=True, exist_ok=True)
    img = Image.open(ROOT / "frontend" / "public" / "samples" / (sample + ".jpg")).convert("RGB")

    # The Retoucher runs its edits on a thread pool, so number and score them under a lock.
    edit, log, lock = gemini.edit_image, [], threading.Lock()

    def capture(image, directive):
        variant, desc = edit(image, directive)
        with lock:
            k = len(log) + 1
            variant.convert("RGB").save(out / "edit{}.jpg".format(k), quality=88)
            prom, abs_ = dg.score_components(variant, box)
            log.append({"k": k, "directive": directive, "prom": prom, "abs": abs_})
        return variant, desc

    agents.gemini.edit_image = capture
    res = agents.run(img, brand=brand, target=box, depth=2)
    if dg.engine_name() != "deepgaze-iie":
        sys.exit("DeepGaze did not load; these scores came from the fallback engine")
    p0, a0 = dg.score_components(img, box)
    json.dump({"sample": sample, "box": box, "base": {"prom": p0, "abs": a0}, "edits": log,
               "tree": res["tree"], "final": res["final_score"]},
              open(out / "run.json", "w", encoding="utf-8"), indent=1)
    print("original  prominence {:.3f}".format(p0))
    for e in log:
        print("edit {}    prominence {:.3f}  {}".format(e["k"], e["prom"], e["directive"][:70]))
    print("kept      prominence {:.3f}".format(res["final_score"]))


if __name__ == "__main__":
    main()
