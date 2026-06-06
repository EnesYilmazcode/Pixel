"""Response models — the single source of truth for the frozen API contract.
Must stay in sync with frontend/src/api.ts + mock.json (see WORK_ALLOCATION.md)."""
from __future__ import annotations

from pydantic import BaseModel

Box = list[float]  # normalized [x, y, w, h] in 0..1


class Distractor(BaseModel):
    region: Box
    share: float
    desc: str


class Fixation(BaseModel):
    x: float
    y: float
    order: int


class PredictResult(BaseModel):
    width: int
    height: int
    attention_score: float
    heatmap_png: str = ""  # data URL; "" => frontend uses CSS fallback
    target_box: Box
    scanpath: list[Fixation] = []
    distractors: list[Distractor] = []


class EditResult(BaseModel):
    variant_png: str
    edit_description: str
    width: int
    height: int


class AgentStep(BaseModel):
    agent: str
    status: str  # idle | running | done | error
    summary: str = ""


class TreeNode(BaseModel):
    id: int
    parent: int | None
    depth: int
    score: float
    status: str  # root | alive | dead | pruned | best
    directive: str = ""


class AgentsResult(BaseModel):
    baseline_score: float
    final_score: float
    delta: float
    brand_brief: dict = {}
    competitive_insights: dict = {}
    heatmap_before: str = ""
    heatmap_after: str = ""
    variant_png: str = ""
    rationale: str = ""
    tree: list[TreeNode] = []  # branch search nodes (for the canvas variant tree)
    iterations: list[AgentStep] = []
