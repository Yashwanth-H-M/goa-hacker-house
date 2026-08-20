"""Build a local hybrid-retrieval index from MSMARCO-XI or a JSONL fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from src.chunking import chunk_records
from src.config import DEFAULT_SETTINGS
from src.data import load_jsonl, load_msmarco_xi
from src.retrieval import HybridIndex


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dataset", default=None, help="Hugging Face dataset id; use ai4bharat/MSMARCO-XI.")
    source.add_argument("--source-jsonl", default=None, help="Normalized JSONL records for local/offline development.")
    parser.add_argument("--language", default="hi", help="MSMARCO-XI language configuration, e.g. hi or ta.")
    parser.add_argument("--split", default="validation", help="Dataset split to load.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum source rows to load from Hugging Face.")
    parser.add_argument("--chunking-strategy", default="sentence", choices=["fixed", "fixed_overlap", "sentence", "semantic_baseline"])
    parser.add_argument("--chunk-size", type=int, default=96)
    parser.add_argument("--chunk-overlap", type=int, default=16)
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    start = perf_counter()

    if args.source_jsonl:
        records = load_jsonl(args.source_jsonl)
        source_name = str(Path(args.source_jsonl))
    else:
        if args.dataset != "ai4bharat/MSMARCO-XI":
            raise ValueError(
                "The official HH Goa Task 2 document names ai4bharat/MSMARCO-XI. "
                "Use that exact dataset unless organizers approve another source."
            )
        records = load_msmarco_xi(args.language, args.split, args.limit, args.dataset)
        source_name = args.dataset

    chunks = chunk_records(
        records,
        strategy=args.chunking_strategy,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    index = HybridIndex(chunks, dimensions=DEFAULT_SETTINGS.embedding_dimensions, rrf_k=DEFAULT_SETTINGS.rrf_k)
    artifact = index.save(args.output_dir, strategy=args.chunking_strategy)

    selected_count = sum(record.selected is True for record in records)
    summary = {
        "source": source_name,
        "language": args.language,
        "records": len(records),
        "selected_records": selected_count,
        "chunks": len(chunks),
        "chunking_strategy": args.chunking_strategy,
        "index_artifact": str(artifact),
        "elapsed_ms": round((perf_counter() - start) * 1000, 3),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
