"""Central config: load backend/.env and expose tunable settings. Import `settings`."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    pinecone_api_key: str = os.getenv("PINECONE_API_KEY", "")
    pinecone_index: str = os.getenv("PINECONE_INDEX", "pixel-ads")

    # Pinned model ids (see PLAN.md — 2.5-flash-image is GA + reliable for the demo).
    gemini_image_model: str = "gemini-2.5-flash-image"
    gemini_text_model: str = "gemini-2.5-flash"

    # Retoucher beam-search params (greedy; see tasks/agent-layer-tasks.md).
    breadth: int = 3
    max_depth: int = 3
    target_score: float = 0.40
    epsilon: float = 0.02

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_pinecone(self) -> bool:
        return bool(self.pinecone_api_key)


settings = Settings()
