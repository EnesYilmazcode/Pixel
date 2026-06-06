"""Branching tree-search — the Retoucher's optimizer.

Greedy beam search over edits. Each round expands the surviving best node(s) into
BREADTH variant edits and scores them. A child that doesn't beat its parent DIES;
alive children compete and only the top BEAM_WIDTH survive to grow next round
(the rest are pruned). Stops at max depth, on hitting the target score, when a
round yields no real improvement, or when every branch dies.

`edit` and `score` are injected so the engine is testable offline (see __main__)
and the same code drives the real run with gemini.edit_image + a DeepGaze scorer.

Returns the FULL tree (root + alive + dead + pruned + best) so the canvas can show
branches dying and others growing, plus the winning image. Never regresses: the
root (original) is the floor, so best_score >= baseline always.
"""
from __future__ import annotations

import itertools
from typing import Callable


def search(
    root_image,
    baseline: float,
    propose: Callable[[object, dict, int], list],
    edit: Callable[[object, object], tuple],
    score: Callable[[object], float],
    *,
    breadth: int = 3,
    max_depth: int = 3,
    beam_width: int = 1,
    target_score: float = 0.40,
    epsilon: float = 0.02,
) -> dict:
    """Run the tree search. See module docstring for the node lifecycle.

    propose(parent_image, parent_node, n) -> list of n directives
    edit(parent_image, directive)         -> (variant_image, description)
    score(variant_image)                  -> attention-on-target in [0, 1]
    """
    ids = itertools.count()
    root = {"id": next(ids), "parent": None, "depth": 0,
            "directive": "original", "score": round(baseline, 4), "status": "root"}
    tree = [root]
    images = {root["id"]: root_image}
    frontier = [root]
    best = root

    for depth in range(1, max_depth + 1):
        prev_best = best["score"]
        children = []
        for parent in frontier:
            for directive in propose(images[parent["id"]], parent, breadth):
                variant, desc = edit(images[parent["id"]], directive)
                s = round(float(score(variant)), 4)
                alive = s > parent["score"]
                node = {"id": next(ids), "parent": parent["id"], "depth": depth,
                        "directive": desc, "score": s,
                        "status": "alive" if alive else "dead"}
                tree.append(node)
                images[node["id"]] = variant
                if alive:
                    children.append(node)

        if not children:
            break  # whole frontier died -> converged

        children.sort(key=lambda n: n["score"], reverse=True)
        if children[0]["score"] > best["score"]:
            best = children[0]
        for n in children[beam_width:]:
            n["status"] = "pruned"  # alive but didn't make the beam
        frontier = children[:beam_width]

        if best["score"] >= target_score:
            break  # good enough
        if best["score"] - prev_best < epsilon:
            break  # diminishing returns

    best["status"] = "best"
    return {
        "tree": tree,
        "best_id": best["id"],
        "best_score": best["score"],
        "best_image": images[best["id"]],
        "rounds": max(n["depth"] for n in tree),
        "improved": best["id"] != root["id"],
    }


def _counts(tree: list[dict]) -> dict:
    out: dict = {}
    for n in tree:
        out[n["status"]] = out.get(n["status"], 0) + 1
    return out


if __name__ == "__main__":
    # Offline self-test: directives ARE target child-scores so the logic is
    # deterministic. Each parent spawns one big improver, one regressor (dies),
    # one small improver (alive but pruned by beam_width=1).
    def propose(_img, parent, n):
        p = parent["score"]
        return [p + 0.12, p - 0.04, p + 0.05][:n]

    def edit(_img, directive):       # directive is the child's absolute score
        return directive, f"edit->{directive:.2f}"

    def score(variant):              # variant carries its score
        return float(variant)

    r = search(root_image="img", baseline=0.10, propose=propose, edit=edit, score=score,
               breadth=3, max_depth=4, beam_width=1, target_score=0.40, epsilon=0.02)
    print("baseline 0.10 -> best", r["best_score"], "| rounds", r["rounds"], "| improved", r["improved"])
    print("node statuses:", _counts(r["tree"]))
    assert r["best_score"] >= 0.10, "regressed below baseline!"
    assert any(n["status"] == "dead" for n in r["tree"]), "no branch died"
    assert sum(n["status"] == "best" for n in r["tree"]) == 1, "must be exactly one best"
    print("OK - branches die, best grows, never regresses.")
