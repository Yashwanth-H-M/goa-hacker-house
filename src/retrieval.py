"""Hybrid Indic semantic, deterministic dense, and BM25 retrieval."""

from __future__ import annotations

from collections import Counter, defaultdict
from heapq import nsmallest
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
from threading import RLock
from time import perf_counter
from typing import Iterable, Sequence

from src.chunking import Chunk

_TOKEN_PATTERN = re.compile(r"[\w\u0900-\u097F]+", re.UNICODE)
_SEMANTIC_MODEL_CACHE: dict[str, object] = {}
_SEMANTIC_MODEL_CACHE_LOCK = RLock()


def tokenize(text: str) -> list[str]:
    """Tokenize Latin and Indic-script text into lowercase lexical units."""

    return _TOKEN_PATTERN.findall(text.lower())


def _stable_bucket(token: str, dimensions: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big") % dimensions


def _normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    return [value / magnitude for value in vector] if magnitude else vector


class HashingEncoder:
    """Small deterministic fallback text encoder used when semantic vectors are unavailable."""

    def __init__(self, dimensions: int = 384) -> None:
        if dimensions <= 0:
            raise ValueError("Embedding dimensions must be positive.")
        self.dimensions = dimensions

    def encode(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        token_counts = Counter(tokenize(text))
        for token, count in token_counts.items():
            bucket = _stable_bucket(token, self.dimensions)
            sign = 1.0 if _stable_bucket(f"sign:{token}", 2) else -1.0
            vector[bucket] += sign * (1.0 + math.log(count))
        return _normalize(vector)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


class BM25Index:
    """A transparent Okapi BM25 implementation over chunk text."""

    def __init__(self, chunks: Sequence[Chunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = list(chunks)
        self.k1 = k1
        self.b = b
        self.document_lengths: list[int] = []
        self.document_frequencies: Counter[str] = Counter()
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for index, chunk in enumerate(self.chunks):
            frequencies = Counter(tokenize(chunk.text))
            self.document_lengths.append(sum(frequencies.values()))
            self.document_frequencies.update(frequencies.keys())
            for token, frequency in frequencies.items():
                self.postings[token].append((index, frequency))
        self.average_document_length = sum(self.document_lengths) / len(self.document_lengths) if self.document_lengths else 0.0

    def score(self, query: str) -> list[float]:
        if not self.chunks:
            return []
        query_tokens = tokenize(query)
        scores = [0.0] * len(self.chunks)
        total_documents = len(self.chunks)
        for term in query_tokens:
            document_frequency = self.document_frequencies.get(term, 0)
            if not document_frequency:
                continue
            idf = math.log(1.0 + (total_documents - document_frequency + 0.5) / (document_frequency + 0.5))
            for index, frequency in self.postings.get(term, ()):
                length_ratio = self.document_lengths[index] / self.average_document_length if self.average_document_length else 0.0
                denominator = frequency + self.k1 * (1.0 - self.b + self.b * length_ratio)
                scores[index] += idf * (frequency * (self.k1 + 1.0) / denominator)
        return scores


@dataclass(frozen=True)
class SearchResult:
    """A ranked chunk and the scores produced by each retrieval channel."""

    chunk: Chunk
    rank: int
    rrf_score: float
    dense_score: float
    sparse_score: float
    semantic_score: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk.chunk_id,
            "parent_passage_id": self.chunk.parent_passage_id,
            "text": self.chunk.text,
            "language": self.chunk.language,
            "query_id": self.chunk.query_id,
            "selected": self.chunk.selected,
            "rank": self.rank,
            "rrf_score": round(self.rrf_score, 8),
            "dense_score": round(self.dense_score, 8),
            "sparse_score": round(self.sparse_score, 8),
            "semantic_score": round(self.semantic_score, 8) if self.semantic_score is not None else None,
        }


def _low_memory_mode() -> bool:
    """Return whether the deployment should prioritize low memory over semantic ranking."""

    return os.getenv("RAG_LOW_MEMORY_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


class HybridIndex:
    """Fuse local Indic semantic vectors, deterministic vectors, and BM25 with RRF.

    The persisted semantic vectors make server startup fast.  The sentence
    embedding model is loaded lazily only when a semantic query is issued.
    An index created without ``semantic_model`` remains fully functional with
    the deterministic hashing-vector and BM25 fallback.
    """

    FORMAT_VERSION = 2

    def __init__(
        self,
        chunks: Sequence[Chunk],
        dimensions: int = 384,
        rrf_k: int = 60,
        semantic_model: str | None = None,
        semantic_vectors: object | None = None,
    ) -> None:
        if not chunks:
            raise ValueError("Cannot create an index with no chunks.")
        self.chunks = list(chunks)
        self.dimensions = dimensions
        self.rrf_k = rrf_k
        self.low_memory_mode = _low_memory_mode()
        self.encoder = HashingEncoder(dimensions)
        # Cloud free tiers may have only 512 MB RAM. Avoid retaining the large
        # per-document hashing matrix in low-memory mode; BM25 remains available.
        self.vectors = [] if self.low_memory_mode else [self.encoder.encode(chunk.text) for chunk in self.chunks]
        self._dense_matrix = None if self.low_memory_mode else self._as_dense_matrix(self.vectors)
        self.bm25 = BM25Index(self.chunks)
        self.semantic_model_name = None if self.low_memory_mode else (semantic_model.strip() if semantic_model else None)
        self._semantic_model = None
        self._semantic_lock = RLock()
        self.semantic_vectors = None

        if semantic_vectors is not None:
            self.semantic_vectors = self._validated_semantic_vectors(semantic_vectors)
        elif self.semantic_model_name:
            self.semantic_vectors = self._encode_semantic_documents([chunk.text for chunk in self.chunks])

    @property
    def semantic_enabled(self) -> bool:
        return self.semantic_model_name is not None and self.semantic_vectors is not None

    @staticmethod
    def _as_dense_matrix(vectors: Sequence[Sequence[float]]):
        """Use NumPy for the local hashing-vector dot product when available."""

        try:
            import numpy as np
        except ImportError:
            return None
        return np.asarray(vectors, dtype=np.float32)

    def _validated_semantic_vectors(self, vectors: object):
        try:
            import numpy as np
        except ImportError as error:  # pragma: no cover - environment setup path
            raise RuntimeError("NumPy is required for persisted semantic vectors.") from error
        array = np.asarray(vectors, dtype=np.float32)
        if array.ndim != 2 or array.shape[0] != len(self.chunks):
            raise ValueError("Semantic vector artifact does not match the indexed chunk count.")
        return array

    def _load_semantic_model(self):
        if not self.semantic_model_name:
            raise RuntimeError("No semantic embedding model was configured for this index.")
        with self._semantic_lock:
            if self._semantic_model is None:
                with _SEMANTIC_MODEL_CACHE_LOCK:
                    cached = _SEMANTIC_MODEL_CACHE.get(self.semantic_model_name)
                    if cached is None:
                        try:
                            from sentence_transformers import SentenceTransformer
                        except ImportError as error:  # pragma: no cover - setup path
                            raise RuntimeError(
                                "Semantic retrieval requires sentence-transformers. Install requirements.txt before starting the server."
                            ) from error
                        cached = SentenceTransformer(self.semantic_model_name, device="cpu")
                        _SEMANTIC_MODEL_CACHE[self.semantic_model_name] = cached
                    self._semantic_model = cached
        return self._semantic_model

    def warm_up(self) -> None:
        """Load the shared semantic query encoder before serving user traffic."""

        if self.semantic_enabled:
            self._load_semantic_model()

    def _uses_e5_prefixes(self) -> bool:
        """Return whether this model requires asymmetric E5 retrieval prefixes."""

        return bool(self.semantic_model_name and "multilingual-e5" in self.semantic_model_name.lower())

    def _semantic_document_inputs(self, texts: list[str]) -> list[str]:
        if self._uses_e5_prefixes():
            return [f"passage: {text}" for text in texts]
        return texts

    def _semantic_query_input(self, query: str) -> str:
        return f"query: {query}" if self._uses_e5_prefixes() else query

    def _encode_semantic_texts(self, texts: list[str]):
        try:
            import numpy as np
        except ImportError as error:  # pragma: no cover - environment setup path
            raise RuntimeError("NumPy is required for semantic retrieval.") from error
        model = self._load_semantic_model()
        with self._semantic_lock:
            vectors = model.encode(
                texts,
                # Larger offline batches reduce semantic index-build time; a
                # one-query request remains a batch of one at serving time.
                batch_size=128,
                show_progress_bar=len(texts) > 128,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
        return np.asarray(vectors, dtype=np.float32)

    def _encode_semantic_documents(self, texts: list[str]):
        return self._encode_semantic_texts(self._semantic_document_inputs(texts))

    def _encode_semantic_query(self, query: str):
        return self._encode_semantic_texts([self._semantic_query_input(query)])[0]

    def _rank_indices(self, scores: Sequence[float], limit: int | None = None) -> list[int]:
        """Rank only the needed candidates, preserving deterministic tie breaks."""

        indices = range(len(scores))
        ordering = lambda index: (-scores[index], self.chunks[index].chunk_id)
        if limit is not None and limit < len(scores):
            return nsmallest(limit, indices, key=ordering)
        return sorted(indices, key=ordering)

    def search(self, query: str, top_k: int = 5, candidate_k: int = 30) -> list[SearchResult]:
        """Run hybrid retrieval without exposing profiling details to callers."""

        results, _ = self._search_with_timings(query, top_k=top_k, candidate_k=candidate_k)
        return results

    def profile_search(
        self,
        query: str,
        top_k: int = 5,
        candidate_k: int = 30,
    ) -> tuple[list[SearchResult], dict[str, float]]:
        """Run the production retrieval path and return per-stage timings in milliseconds."""

        return self._search_with_timings(query, top_k=top_k, candidate_k=candidate_k)

    def _search_with_timings(
        self,
        query: str,
        top_k: int,
        candidate_k: int,
    ) -> tuple[list[SearchResult], dict[str, float]]:
        if not query or not query.strip():
            raise ValueError("A non-empty query is required.")
        if top_k <= 0:
            raise ValueError("top_k must be positive.")
        if candidate_k <= 0:
            raise ValueError("candidate_k must be positive.")

        total_started = perf_counter()
        embedding_started = total_started
        query_vector = self.encoder.encode(query)
        semantic_scores: list[float] | None = None
        if self.semantic_enabled:
            query_semantic_vector = self._encode_semantic_query(query)
        else:
            query_semantic_vector = None
        embedding_ms = (perf_counter() - embedding_started) * 1000

        retrieval_started = perf_counter()
        if self.low_memory_mode:
            dense_scores = [0.0] * len(self.chunks)
            dense_ranked: list[int] = []
        else:
            dense_scores = (
                (self._dense_matrix @ query_vector).tolist()
                if self._dense_matrix is not None
                else [cosine_similarity(query_vector, vector) for vector in self.vectors]
            )
            dense_ranked = self._rank_indices(dense_scores, candidate_k)
        sparse_scores = self.bm25.score(query)
        sparse_ranked = self._rank_indices(sparse_scores, candidate_k)

        semantic_ranked: list[int] = []
        if query_semantic_vector is not None:
            semantic_scores = (self.semantic_vectors @ query_semantic_vector).tolist()
            semantic_ranked = self._rank_indices(semantic_scores, candidate_k)

        fused_scores: defaultdict[int, float] = defaultdict(float)
        for ranked_indices in (dense_ranked, sparse_ranked, semantic_ranked):
            for rank, index in enumerate(ranked_indices, start=1):
                fused_scores[index] += 1.0 / (self.rrf_k + rank)

        ranked = sorted(
            fused_scores,
            key=lambda index: (
                -fused_scores[index],
                -(semantic_scores[index] if semantic_scores is not None else dense_scores[index]),
                self.chunks[index].chunk_id,
            ),
        )[:top_k]
        results = [
            SearchResult(
                chunk=self.chunks[index],
                rank=rank,
                rrf_score=fused_scores[index],
                dense_score=dense_scores[index],
                sparse_score=sparse_scores[index],
                semantic_score=semantic_scores[index] if semantic_scores is not None else None,
            )
            for rank, index in enumerate(ranked, start=1)
        ]
        search_ms = (perf_counter() - retrieval_started) * 1000
        total_ms = (perf_counter() - total_started) * 1000
        return results, {
            "embed_ms": embedding_ms,
            "search_ms": search_ms,
            "total_ms": total_ms,
        }

    def save(self, output_dir: str | Path, strategy: str) -> Path:
        """Persist a portable index plus optional normalized semantic vectors."""

        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        semantic_vectors_file = None
        if self.semantic_vectors is not None:
            try:
                import numpy as np
            except ImportError as error:  # pragma: no cover - environment setup path
                raise RuntimeError("NumPy is required to save semantic vectors.") from error
            semantic_vectors_file = "semantic_vectors.npy"
            np.save(destination / semantic_vectors_file, self.semantic_vectors, allow_pickle=False)

        artifact = {
            "format_version": self.FORMAT_VERSION,
            "encoder": "hashing-vector-baseline",
            "dimensions": self.dimensions,
            "rrf_k": self.rrf_k,
            "strategy": strategy,
            "chunk_count": len(self.chunks),
            "semantic_model": self.semantic_model_name,
            "semantic_vectors_file": semantic_vectors_file,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }
        target = destination / "index.json"
        target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    @classmethod
    def load(cls, index_dir: str | Path) -> "HybridIndex":
        source = Path(index_dir) / "index.json"
        if not source.exists():
            raise FileNotFoundError(f"Index artifact not found: {source}")
        payload = json.loads(source.read_text(encoding="utf-8"))
        format_version = payload.get("format_version")
        if format_version not in {1, cls.FORMAT_VERSION}:
            raise ValueError("Unsupported index format version.")
        chunks = [Chunk.from_dict(chunk) for chunk in payload["chunks"]]
        semantic_vectors = None
        semantic_model = payload.get("semantic_model") if format_version == cls.FORMAT_VERSION else None
        semantic_vectors_file = payload.get("semantic_vectors_file") if format_version == cls.FORMAT_VERSION else None
        if _low_memory_mode():
            semantic_model = None
            semantic_vectors_file = None
        if semantic_model and semantic_vectors_file:
            try:
                import numpy as np
            except ImportError as error:  # pragma: no cover - environment setup path
                raise RuntimeError("NumPy is required to load semantic vectors.") from error
            vector_path = source.parent / str(semantic_vectors_file)
            if not vector_path.exists():
                raise FileNotFoundError(f"Semantic vector artifact not found: {vector_path}")
            semantic_vectors = np.load(vector_path, allow_pickle=False)
        return cls(
            chunks=chunks,
            dimensions=int(payload["dimensions"]),
            rrf_k=int(payload["rrf_k"]),
            semantic_model=str(semantic_model) if semantic_model else None,
            semantic_vectors=semantic_vectors,
        )
