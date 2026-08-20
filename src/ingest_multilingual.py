"""Build capped real-corpus indexes for Hindi, Kannada, and Telugu."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from src.chunking import chunk_records
from src.config import DEFAULT_SETTINGS
from src.data import load_msmarco_xi
from src.languages import DEFAULT_LANGUAGE_ORDER, require_supported_language
from src.retrieval import HybridIndex


def build_language_index(
    language: str,
    split: str,
    limit: int,
    output_root: Path,
    chunking_strategy: str,
    chunk_size: int,
    chunk_overlap: int,
) -> dict[str, Any]:
    """Ingest one sanctioned language configuration and persist its index."""

    option = require_supported_language(language)
    start = perf_counter()
    records = load_msmarco_xi(language=option.config, split=split, limit=limit)
    chunks = chunk_records(
        records,
        strategy=chunking_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    index = HybridIndex(
        chunks,
        dimensions=DEFAULT_SETTINGS.embedding_dimensions,
        rrf_k=DEFAULT_SETTINGS.rrf_k,
        semantic_model=DEFAULT_SETTINGS.semantic_model,
    )
    target = output_root / option.config
    artifact = index.save(target, strategy=chunking_strategy)
    return {
        "language": option.config,
        "display_name": option.display_name,
        "split": split,
        "source_rows_requested": limit,
        "passages": len(records),
        "selected_passages": sum(record.selected is True for record in records),
        "chunks": len(chunks),
        "chunking_strategy": chunking_strategy,
        "index_dir": str(target),
        "index_artifact": str(artifact),
        "elapsed_ms": round((perf_counter() - start) * 1000, 3),
    }


def _existing_summaries(output_root: Path) -> dict[str, dict[str, Any]]:
    manifest_path = output_root / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {
            item["language"]: item
            for item in manifest.get("languages", [])
            if isinstance(item, dict) and isinstance(item.get("language"), str)
        }
    except (json.JSONDecodeError, OSError):
        return {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--languages",
        nargs="+",
        default=list(DEFAULT_LANGUAGE_ORDER),
        help="MSMARCO-XI language scopes to index; defaults to hi kn te.",
    )
    parser.add_argument("--split", default="validation")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum source rows per language.")
    parser.add_argument("--output-root", default="index/multilingual")
    parser.add_argument(
        "--chunking-strategy",
        default="sentence",
        choices=["fixed", "fixed_overlap", "sentence", "semantic", "semantic_baseline", "passage"],
    )
    parser.add_argument("--chunk-size", type=int, default=96)
    parser.add_argument("--chunk-overlap", type=int, default=16)
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Preserve a completed language index and its manifest entry instead of rebuilding it.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.limit < 1:
        raise ValueError("--limit must be at least 1.")
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    existing = _existing_summaries(output_root)
    summaries = dict(existing)

    for language in args.languages:
        option = require_supported_language(language)
        index_path = output_root / option.config / "index.json"
        if args.skip_existing and index_path.exists() and option.config in existing:
            print(f"Preserving completed {option.display_name} index at {index_path}")
            continue
        summaries[option.config] = build_language_index(
            language=option.config,
            split=args.split,
            limit=args.limit,
            output_root=output_root,
            chunking_strategy=args.chunking_strategy,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )

    ordered_summaries = [summaries[language] for language in DEFAULT_LANGUAGE_ORDER if language in summaries]
    manifest = {
        "dataset": "ai4bharat/MSMARCO-XI",
        "languages": ordered_summaries,
        "total_chunks": sum(item["chunks"] for item in ordered_summaries),
        "total_passages": sum(item["passages"] for item in ordered_summaries),
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
