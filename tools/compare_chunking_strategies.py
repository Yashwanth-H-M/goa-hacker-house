"""Compare provenance-preserving chunking strategies on saved MSMARCO-XI data.

This benchmark intentionally uses local deterministic retrieval only. It isolates
chunking effects without repeat cloud embedding, STT, or generation calls and
writes a competition-ready table with retrieval quality and latency statistics.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from statistics import median
import sys
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.chunking import chunk_records
from src.config import DEFAULT_SETTINGS
from src.data import load_jsonl
from src.evaluate import percentile
from src.languages import DEFAULT_LANGUAGE_ORDER, require_supported_language
from src.retrieval import HybridIndex

STRATEGIES = ("fixed", "fixed_overlap", "sentence", "semantic", "passage")


def evaluate(index: HybridIndex, records: list, query_limit: int) -> dict[str, float | int]:
    grouped: dict[str, list] = defaultdict(list)
    for record in records:
        grouped[record.query_id].append(record)

    recall_at_5: list[float] = []
    recall_at_10: list[float] = []
    reciprocal_rank: list[float] = []
    latency_ms: list[float] = []

    for group in grouped.values():
        query = next((record.query for record in group if record.query), None)
        relevant_ids = {record.passage_id for record in group if record.selected is True}
        if not query or not relevant_ids:
            continue
        started = perf_counter()
        results = index.search(query, top_k=10)
        latency_ms.append((perf_counter() - started) * 1000)
        returned_parents = [result.chunk.parent_passage_id for result in results]
        recall_at_5.append(float(bool(set(returned_parents[:5]) & relevant_ids)))
        recall_at_10.append(float(bool(set(returned_parents[:10]) & relevant_ids)))
        first_rank = next(
            (rank for rank, passage_id in enumerate(returned_parents, start=1) if passage_id in relevant_ids),
            None,
        )
        reciprocal_rank.append(1.0 / first_rank if first_rank else 0.0)
        if len(latency_ms) >= query_limit:
            break

    if not latency_ms:
        raise ValueError("No evaluable query groups found.")
    return {
        "queries": len(latency_ms),
        "recall_at_5": sum(recall_at_5) / len(recall_at_5),
        "recall_at_10": sum(recall_at_10) / len(recall_at_10),
        "mrr": sum(reciprocal_rank) / len(reciprocal_rank),
        "p50_ms": median(latency_ms),
        "p70_ms": percentile(latency_ms, 70),
        "p100_ms": max(latency_ms),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--eval-root", default="artifacts/evaluation")
    result.add_argument("--output", default="artifacts/evaluation/chunking_strategy_comparison.md")
    result.add_argument("--queries-per-language", type=int, default=100)
    result.add_argument("--chunk-size", type=int, default=96)
    result.add_argument("--chunk-overlap", type=int, default=16)
    return result


def main() -> None:
    args = parser().parse_args()
    if args.queries_per_language < 1:
        raise ValueError("--queries-per-language must be at least 1.")

    rows: list[dict[str, float | int | str]] = []
    eval_root = Path(args.eval_root)
    for language in DEFAULT_LANGUAGE_ORDER:
        option = require_supported_language(language)
        records = list(load_jsonl(eval_root / f"{language}_official_validation_1000.jsonl"))
        for strategy in STRATEGIES:
            build_started = perf_counter()
            chunks = chunk_records(
                records,
                strategy=strategy,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
            )
            index = HybridIndex(
                chunks,
                dimensions=DEFAULT_SETTINGS.embedding_dimensions,
                rrf_k=DEFAULT_SETTINGS.rrf_k,
                semantic_model=None,
            )
            build_ms = (perf_counter() - build_started) * 1000
            measured = evaluate(index, records, args.queries_per_language)
            rows.append({
                "language": option.display_name,
                "strategy": strategy,
                "chunks": len(chunks),
                "build_ms": build_ms,
                **measured,
            })
            print(
                f"{option.display_name} | {strategy} | "
                f"R@5={measured['recall_at_5']:.4f} | MRR={measured['mrr']:.4f}"
            )

    lines = [
        "# Chunking Strategy Comparison",
        "",
        "This reproducible development benchmark compares five provenance-preserving chunking strategies over the saved official `ai4bharat/MSMARCO-XI` validation records. Each strategy is measured with the same 100 evaluable query groups per language and deterministic hybrid retrieval (hashing-vector dense retrieval + BM25 + RRF). It deliberately excludes remote semantic embedding, STT, and answer generation so the table isolates chunking and local retrieval effects.",
        "",
        "| Language | Strategy | Chunks | Build (ms) | Queries | Recall@5 | Recall@10 | MRR | P50 retrieval (ms) | P70 retrieval (ms) | P100 retrieval (ms) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {language} | {strategy} | {chunks} | {build_ms:.3f} | {queries} | "
            "{recall_at_5:.4f} | {recall_at_10:.4f} | {mrr:.4f} | "
            "{p50_ms:.3f} | {p70_ms:.3f} | {p100_ms:.3f} |".format(**row)
        )

    lines.extend([
        "",
        "## Interpretation guidance",
        "",
        "Select the default strategy from the measured quality/latency trade-off rather than from a conceptual preference. Any production semantic-embedding or generation benchmark must be reported separately because its external-model latency is not represented in this local retrieval-only table.",
    ])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
