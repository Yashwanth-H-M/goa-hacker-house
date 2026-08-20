"""Official-benchmark adapter for Contextline's production hybrid retriever.

The adapter preserves the supplied benchmark's public contract while measuring
the application's actual steady-state hybrid retrieval path.  It does not claim
FAISS usage: the current system uses persisted semantic vectors, BM25, hashing
vectors, and reciprocal-rank fusion.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from threading import RLock

from src.retrieval import HybridIndex, SearchResult


@dataclass(frozen=True)
class BenchmarkResponse:
    """Search output and the official benchmark timing fields in milliseconds."""

    results: list[SearchResult]
    embed_ms: float
    search_ms: float
    total_ms: float


_INDEX: HybridIndex | None = None
_INDEX_LOCK = RLock()
_DEFAULT_INDEX_DIR = Path("index") / "semantic_multilingual" / "hi"
_WARMUP_QUERY = "What is retrieval augmented generation?"


def _index_dir() -> Path:
    configured = os.getenv("RAG_BENCHMARK_INDEX_DIR", "").strip()
    return Path(configured) if configured else _DEFAULT_INDEX_DIR


def _get_index() -> HybridIndex:
    global _INDEX
    with _INDEX_LOCK:
        if _INDEX is None:
            _INDEX = HybridIndex.load(_index_dir())
    return _INDEX


def warmup() -> None:
    """Load the production index and execute one untimed semantic retrieval."""

    index = _get_index()
    index.warm_up()
    index.profile_search(_WARMUP_QUERY, top_k=5)


def search(query: str, top_k: int = 5) -> BenchmarkResponse:
    """Measure one production hybrid-retrieval call after warm-up."""

    results, timings = _get_index().profile_search(query, top_k=top_k)
    return BenchmarkResponse(
        results=results,
        embed_ms=timings["embed_ms"],
        search_ms=timings["search_ms"],
        total_ms=timings["total_ms"],
    )
