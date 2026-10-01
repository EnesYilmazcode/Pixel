"""Try hand-written edit prompts on one sample ad and keep every result.

    python scripts/try_edits.py red-bull "Red Bull" "remove the phone ..." "..."

Each prompt is one Nano Banana edit of the original. Every edit is re-scored by DeepGaze
against the sample's fixed brand box, judged for brand fit, and run through the
reward-hack guard, the same checks /optimize/step applies. Writes results/<sample>/edit<k>.jpg
and appends to results/<sample>/run.json. Needs GEMINI_API_KEY.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
import deepgaze_runner as dg  # noqa: E402
import eval_guard  # noqa: E402
import gemini  # noqa: E402
from capture_run import target_box  # noqa: E402


def main():
    sample, brand, prompts = sys.argv[1], sys.argv[2], sys.argv[3:]
    box = target_box(sample)
    out = ROOT / "results" / sample
    out.mkdir(parents=True, exist_ok=True)
    path = out / "run.json"
    img = Image.open(ROOT / "frontend" / "public" / "samples" / (sample + ".jpg")).convert("RGB")
    p0, a0 = dg.score_components(img, box)
    if dg.engine_name() != "deepgaze-iie":
        sys.exit("DeepGaze did not load; refusing to score with the fallback engine")
    run = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "sample": sample, "brand": brand, "box": box, "base": {"prom": p0, "abs": a0}, "edits": []}
    print("original  prominence {:.1f}".format(p0 * 100))
    for directive in prompts:
        variant, desc = gemini.edit_image(img, directive)
        if desc.startswith("["):
            sys.exit("edit failed: " + desc[:80])
        k = len(run["edits"]) + 1
        variant.convert("RGB").save(out / "edit{}.jpg".format(k), quality=90)
        prom, abs_ = dg.score_components(variant, box)
        judge, reason = gemini.judge(variant, brand)
        v = eval_guard.verdict(img, variant, ratio_before=p0, ratio_after=prom,
                               target_sal_before=a0, target_sal_after=abs_, target_box=box)
        kept = prom > p0 and judge >= gemini.settings.judge_gate and v["decision"] == "accept"
        run["edits"].append({"k": k, "directive": directive, "prom": prom, "abs": abs_,
                             "judge": judge, "judge_reason": reason, "guard": v["decision"],
                             "guard_reasons": v["reasons"], "outside": v["outside"], "kept": kept})
        path.write_text(json.dumps(run, indent=1), encoding="utf-8")
        print("edit {}  prominence {:.1f} ({:+.1f})  salience {:.3f} -> {:.3f}  judge {:.2f}  guard {}  {}".format(
            k, prom * 100, (prom - p0) * 100, a0, abs_, judge, v["decision"], "KEPT" if kept else ""))
        print("        ", v["reasons"][0])


if __name__ == "__main__":
    main()
