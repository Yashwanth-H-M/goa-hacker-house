"""Chunking strategies for the RAG baseline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable

from src.data import PassageRecord


@dataclass(frozen=True)
class Chunk:
    """A searchable text span with stable source provenance."""

    chunk_id: str
    parent_passage_id: str
    text: str
    language: str
    query_id: str
    selected: bool | None
    chunk_index: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "Chunk":
        return cls(
            chunk_id=str(payload["chunk_id"]),
            parent_passage_id=str(payload["parent_passage_id"]),
            text=str(payload["text"]),
            language=str(payload["language"]),
            query_id=str(payload["query_id"]),
            selected=payload.get("selected") if isinstance(payload.get("selected"), bool) else None,
            chunk_index=int(payload["chunk_index"]),
        )


def _word_windows(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    if size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size")

    step = size - overlap
    return [" ".join(words[start : start + size]) for start in range(0, len(words), step)]


def fixed_size_chunks(record: PassageRecord, chunk_size: int = 96, chunk_overlap: int = 16) -> list[Chunk]:
    """Produce fixed-size word windows as the explicit baseline strategy."""

    return [
        Chunk(
            chunk_id=f"{record.passage_id}:chunk:{index}",
            parent_passage_id=record.passage_id,
            text=text,
            language=record.language,
            query_id=record.query_id,
            selected=record.selected,
            chunk_index=index,
        )
        for index, text in enumerate(_word_windows(record.text, chunk_size, chunk_overlap))
        if text.strip()
    ]


def sentence_aware_chunks(record: PassageRecord, max_words: int = 96) -> list[Chunk]:
    """Group adjacent sentence-like spans without breaking a sentence when possible."""

    if max_words <= 0:
        raise ValueError("max_words must be positive")

    sentences = [segment.strip() for segment in re.split(r"(?<=[.!?।])\s+", record.text) if segment.strip()]
    if not sentences:
        return []

    grouped: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        sentence_words = len(sentence.split())
        if current and current_words + sentence_words > max_words:
            grouped.append(" ".join(current))
            current = []
            current_words = 0
        if sentence_words > max_words:
            if current:
                grouped.append(" ".join(current))
                current = []
                current_words = 0
            grouped.extend(_word_windows(sentence, max_words, 0))
            continue
        current.append(sentence)
        current_words += sentence_words
    if current:
        grouped.append(" ".join(current))

    return [
        Chunk(
            chunk_id=f"{record.passage_id}:sentence:{index}",
            parent_passage_id=record.passage_id,
            text=text,
            language=record.language,
            query_id=record.query_id,
            selected=record.selected,
            chunk_index=index,
        )
        for index, text in enumerate(grouped)
        if text.strip()
    ]


def metadata_aware_chunks(record: PassageRecord) -> list[Chunk]:
    """Keep an original passage intact while retaining all source metadata.

    This is a useful comparison point for MSMARCO-XI because many passages are
    already concise. It proves whether splitting helps rather than assuming it.
    """

    text = record.text.strip()
    if not text:
        return []
    return [
        Chunk(
            chunk_id=f"{record.passage_id}:passage:0",
            parent_passage_id=record.passage_id,
            text=text,
            language=record.language,
            query_id=record.query_id,
            selected=record.selected,
            chunk_index=0,
        )
    ]


def _token_overlap(left: str, right: str) -> float:
    """Return Jaccard token overlap for a transparent local semantic proxy."""

    left_tokens = {token.lower() for token in re.findall(r"[\w\u0900-\u097F]+", left, flags=re.UNICODE)}
    right_tokens = {token.lower() for token in re.findall(r"[\w\u0900-\u097F]+", right, flags=re.UNICODE)}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def adaptive_semantic_chunks(
    record: PassageRecord,
    max_words: int = 96,
    similarity_threshold: float = 0.18,
    minimum_words_before_split: int = 24,
) -> list[Chunk]:
    """Group sentences until a topical shift or size boundary is observed.

    The approach is deliberately different from fixed windows and sentence-size
    packing: it evaluates the token-set similarity of adjacent sentences, then
    starts a new chunk only when there is a probable topical boundary and the
    current chunk already has enough context. All MSMARCO-XI provenance fields
    remain attached to every produced chunk.
    """

    if max_words <= 0:
        raise ValueError("max_words must be positive")
    if not 0.0 <= similarity_threshold <= 1.0:
        raise ValueError("similarity_threshold must be between 0 and 1")

    sentences = [segment.strip() for segment in re.split(r"(?<=[.!?।])\s+", record.text) if segment.strip()]
    if not sentences:
        return []

    grouped: list[str] = []
    current: list[str] = []
    current_words = 0
    previous_sentence: str | None = None
    for sentence in sentences:
        sentence_words = len(sentence.split())
        topical_break = (
            previous_sentence is not None
            and current_words >= minimum_words_before_split
            and _token_overlap(previous_sentence, sentence) < similarity_threshold
        )
        size_break = current and current_words + sentence_words > max_words
        if current and (topical_break or size_break):
            grouped.append(" ".join(current))
            current = []
            current_words = 0
        if sentence_words > max_words:
            if current:
                grouped.append(" ".join(current))
                current = []
                current_words = 0
            grouped.extend(_word_windows(sentence, max_words, 0))
        else:
            current.append(sentence)
            current_words += sentence_words
        previous_sentence = sentence
    if current:
        grouped.append(" ".join(current))

    return [
        Chunk(
            chunk_id=f"{record.passage_id}:semantic:{index}",
            parent_passage_id=record.passage_id,
            text=text,
            language=record.language,
            query_id=record.query_id,
            selected=record.selected,
            chunk_index=index,
        )
        for index, text in enumerate(grouped)
        if text.strip()
    ]


def chunk_records(
    records: Iterable[PassageRecord],
    strategy: str = "sentence",
    chunk_size: int = 96,
    chunk_overlap: int = 16,
) -> list[Chunk]:
    """Chunk records with distinct, provenance-preserving strategies."""

    strategy_name = strategy.lower().strip()
    chunks: list[Chunk] = []
    for record in records:
        if strategy_name == "fixed":
            chunks.extend(fixed_size_chunks(record, chunk_size, 0))
        elif strategy_name == "fixed_overlap":
            chunks.extend(fixed_size_chunks(record, chunk_size, chunk_overlap))
        elif strategy_name == "sentence":
            chunks.extend(sentence_aware_chunks(record, chunk_size))
        elif strategy_name in {"semantic", "semantic_baseline"}:
            chunks.extend(adaptive_semantic_chunks(record, chunk_size))
        elif strategy_name in {"passage", "metadata"}:
            chunks.extend(metadata_aware_chunks(record))
        else:
            raise ValueError(
                f"Unsupported chunking strategy '{strategy}'. "
                "Use fixed, fixed_overlap, sentence, semantic, or passage."
            )

    if not chunks:
        raise ValueError("Chunking produced no searchable text.")
    return chunks
