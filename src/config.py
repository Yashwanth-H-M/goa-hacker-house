"""Configuration helpers for the local RAG application."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> None:
    """Load simple KEY=VALUE pairs without adding a third-party dependency.

    Existing environment values always win, so deployment environments can
    inject credentials without writing a local file.
    """

    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (key not in os.environ or not os.environ[key]):
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    """Runtime settings and optional provider credentials."""

    embedding_dimensions: int = 384
    rrf_k: int = 60
    default_top_k: int = 5
    minimum_similarity: float = -0.05
    minimum_semantic_similarity: float = 0.45
    minimum_semantic_margin: float = 0.015
    semantic_model: str | None = "intfloat/multilingual-e5-small"
    sarvam_api_key: str | None = None
    sarvam_model: str = "saaras:v3"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    @classmethod
    def from_environment(cls) -> "Settings":
        semantic_model = os.getenv("RAG_SEMANTIC_MODEL", "intfloat/multilingual-e5-small").strip()
        return cls(
            embedding_dimensions=int(os.getenv("RAG_EMBEDDING_DIMENSIONS", "384")),
            rrf_k=int(os.getenv("RAG_RRF_K", "60")),
            default_top_k=int(os.getenv("RAG_TOP_K", "5")),
            minimum_similarity=float(os.getenv("RAG_MINIMUM_SIMILARITY", "-0.05")),
            minimum_semantic_similarity=float(os.getenv("RAG_MINIMUM_SEMANTIC_SIMILARITY", "0.45")),
            minimum_semantic_margin=float(os.getenv("RAG_MINIMUM_SEMANTIC_MARGIN", "0.015")),
            semantic_model=semantic_model or None,
            sarvam_api_key=os.getenv("SARVAM_API_KEY") or None,
            sarvam_model=os.getenv("SARVAM_STT_MODEL", "saaras:v3"),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        )


load_dotenv()
DEFAULT_SETTINGS = Settings.from_environment()
