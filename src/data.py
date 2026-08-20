"""Data adapters for the competition-linked ai4bharat/MSMARCO-XI corpus."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any, Iterable, Iterator

from src.languages import require_supported_language


DATASET_NAME = "ai4bharat/MSMARCO-XI"


@dataclass(frozen=True)
class PassageRecord:
    """A flattened passage with enough provenance for retrieval and evaluation."""

    passage_id: str
    query_id: str
    text: str
    language: str
    selected: bool | None = None
    query: str | None = None
    query_type: str | None = None
    source_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PassageRecord":
        return cls(
            passage_id=str(payload["passage_id"]),
            query_id=str(payload.get("query_id", "")),
            text=str(payload["text"]),
            language=str(payload.get("language", "unknown")),
            selected=payload.get("selected"),
            query=payload.get("query"),
            query_type=payload.get("query_type"),
            source_index=payload.get("source_index"),
        )


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return list(value)


def flatten_msmarco_xi_row(row: dict[str, Any], language: str) -> Iterator[PassageRecord]:
    """Flatten one official MSMARCO-XI row into individual translated passages.

    The current public repository uses a default dataset configuration with one
    parquet file per language. Its rows expose ``Eng_Query`` and a ``passages``
    mapping containing parallel ``Translated_passages`` and ``is_selected``
    arrays. The adapter tolerates the historic ``query`` field for fixtures and
    older cached schemas.
    """

    passages = row.get("passages")
    if not isinstance(passages, dict):
        raise ValueError("Expected a 'passages' mapping in the MSMARCO-XI row.")

    translated = _as_list(passages.get("Translated_passages"))
    selected = _as_list(passages.get("is_selected"))
    if not translated:
        raise ValueError("No translated passages found in the MSMARCO-XI row.")

    query_id = str(row.get("query_id", "unknown"))
    query = row.get("query") or row.get("Eng_Query")
    query_type = row.get("query_type")

    for index, text in enumerate(translated):
        if not isinstance(text, str) or not text.strip():
            continue
        label = bool(selected[index]) if index < len(selected) else None
        yield PassageRecord(
            passage_id=f"{language}:{query_id}:{index}",
            query_id=query_id,
            text=text.strip(),
            language=language,
            selected=label,
            query=query if isinstance(query, str) else None,
            query_type=query_type if isinstance(query_type, str) else None,
            source_index=index,
        )


def _download_validation_parquet(language: str, dataset_name: str, data_dir: Path) -> Path:
    """Download the official validation parquet for one configured language."""

    if dataset_name != DATASET_NAME:
        raise ValueError(
            "The official HH Goa Task 2 document names ai4bharat/MSMARCO-XI. "
            "Use that exact dataset unless organizers approve another source."
        )
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as error:  # pragma: no cover - manual setup path
        raise RuntimeError(
            "The Hugging Face loader is required. Install: pip install -r requirements-hf.txt"
        ) from error

    option = require_supported_language(language)
    direct_path = data_dir / option.validation_parquet
    if direct_path.exists() and direct_path.stat().st_size > 0:
        return direct_path
    local_path = hf_hub_download(
        repo_id=dataset_name,
        repo_type="dataset",
        filename=option.validation_parquet,
        local_dir=str(data_dir),
        token=os.getenv("HF_TOKEN") or None,
    )
    return Path(local_path)


def load_msmarco_xi(
    language: str,
    split: str = "validation",
    limit: int | None = None,
    dataset_name: str = DATASET_NAME,
    data_dir: str | Path = "data/msmarco-xi",
) -> list[PassageRecord]:
    """Download and flatten a bounded official language slice.

    The public MSMARCO-XI repository currently exposes the selected languages as
    large parquet files under its default configuration. Reading with PyArrow
    batches avoids materialising the full file in memory while preserving the
    exact official source and a reproducible local copy.
    """

    if split != "validation":
        raise ValueError("The configured multilingual development loader currently supports split='validation' only.")
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1 when supplied.")
    try:
        import pyarrow.parquet as pq
    except ImportError as error:  # pragma: no cover - manual setup path
        raise RuntimeError(
            "PyArrow is required for official parquet ingestion. Install: pip install -r requirements-hf.txt"
        ) from error

    option = require_supported_language(language)
    parquet_path = _download_validation_parquet(option.config, dataset_name, Path(data_dir))
    records: list[PassageRecord] = []
    source_rows = 0
    parquet_file = pq.ParquetFile(parquet_path)
    for batch in parquet_file.iter_batches(batch_size=128):
        for row in batch.to_pylist():
            records.extend(flatten_msmarco_xi_row(dict(row), option.config))
            source_rows += 1
            if limit is not None and source_rows >= limit:
                break
        if limit is not None and source_rows >= limit:
            break

    if not records:
        raise ValueError("The selected dataset slice produced no usable passages.")
    return records


def load_jsonl(path: str | Path) -> list[PassageRecord]:
    """Load a development fixture containing one normalized passage per JSONL line."""

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"JSONL fixture does not exist: {source}")

    records: list[PassageRecord] = []
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(PassageRecord.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                raise ValueError(f"Invalid JSONL record on line {line_number} of {source}") from error

    if not records:
        raise ValueError(f"No records found in JSONL fixture: {source}")
    return records


def write_jsonl(records: Iterable[PassageRecord], path: str | Path) -> None:
    """Write normalized records for debugging or a frozen evaluation fixture."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
