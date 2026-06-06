"""Central config: load backend/.env and expose tunable settings. Import `settings`."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

# LangChain orchestration (the LCEL chain) needs no API key and no network. LangSmith
# *tracing* is optional observability and DOES need a key — if tracing is switched on
# without one, disable it so we don't spam failed-upload (401) errors every run.
if os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("1", "true"):
    if not (os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")):
        os.environ["LANGCHAIN_TRACING_V2"] = "false"


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    pinecone_api_key: str = os.getenv("PINECONE_API_KEY", "")
    pinecone_index: str = os.getenv("PINECONE_INDEX", "pixel-ads")

    # Pinned model ids (see PLAN.md — 2.5-flash-image is GA + reliable for the demo).
    gemini_image_model: str = "gemini-2.5-flash-image"
    gemini_text_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768  # must match the Pinecone index dimension

    # Retoucher beam-search params (greedy; see tasks/agent-layer-tasks.md).
    breadth: int = 3
    max_depth: int = 3
    target_score: float = 0.40
    epsilon: float = 0.02

    # Scout: live web grounding (Gemini + Google Search). Off via WEB_SEARCH=0.
    web_search: bool = os.getenv("WEB_SEARCH", "1") != "0"
    web_k: int = 4  # max rival campaigns to pull from the live web per run

    # Judge (LLM-as-judge): gates the Retoucher's fitness so a garish, high-attention
    # but off-brand variant can't win. Off via JUDGE=0. Gate = min acceptable brand-fit.
    use_judge: bool = os.getenv("JUDGE", "1") != "0"
    judge_gate: float = 0.45

    # LangChain orchestrates the Director as an LCEL chain (no API key / network needed).
    # Off via LANGCHAIN=0 (falls back to plain sequential run). Optional LangSmith tracing
    # self-enables only when LANGCHAIN_TRACING_V2 + a LangSmith key are both set.
    use_langchain: bool = os.getenv("LANGCHAIN", "1") != "0"

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_pinecone(self) -> bool:
        return bool(self.pinecone_api_key)


settings = Settings()
