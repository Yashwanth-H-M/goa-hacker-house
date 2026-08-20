"""Benchmark the completed multilingual indexes with official MSMARCO-XI labels.

This utility runs a deterministic bounded sample for each language, reports
retrieval quality and P50/P70/P100 latency, and records the exact evaluation
inputs for competition evidence.
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

from src.data import load_jsonl
from src.evaluate import percentile
from src.languages import DEFAULT_LANGUAGE_ORDER, require_supported_language
from src.retrieval import HybridIndex


def evaluate_language(index_dir: Path, eval_jsonl: Path, max_queries: int) -> dict[str, float | int | str]:
    index = HybridIndex.load(index_dir)
    grouped: dict[str, list] = defaultdict(list)
    for record in load_jsonl(eval_jsonl):
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
        start = perf_counter()
        results = index.search(query, top_k=10)
        latency_ms.append((perf_counter() - start) * 1000)
        returned_parents = [result.chunk.parent_passage_id for result in results]
        recall_at_5.append(float(bool(set(returned_parents[:5]) & relevant_ids)))
        recall_at_10.append(float(bool(set(returned_parents[:10]) & relevant_ids)))
        first_rank = next(
            (rank for rank, passage_id in enumerate(returned_parents, start=1) if passage_id in relevant_ids),
            None,
        )
        reciprocal_rank.append(1.0 / first_rank if first_rank else 0.0)
        if len(latency_ms) >= max_queries:
            break

    evaluated = len(latency_ms)
    if not evaluated:
        raise ValueError(f"No evaluable query groups found in {eval_jsonl}.")
    return {
        "queries_evaluated": evaluated,
        "recall_at_5": sum(recall_at_5) / evaluated,
        "recall_at_10": sum(recall_at_10) / evaluated,
        "mrr": sum(reciprocal_rank) / evaluated,
        "p50": median(latency_ms),
        "p70": percentile(latency_ms, 70),
        "p100": max(latency_ms),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-root", default="index/multilingual")
    parser.add_argument("--eval-root", default="artifacts/evaluation")
    parser.add_argument("--queries-per-language", type=int, default=100)
    parser.add_argument("--output", default="artifacts/evaluation/multilingual_benchmark.md")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.queries_per_language < 1:
        raise ValueError("--queries-per-language must be at least 1.")

    index_root = Path(args.index_root)
    eval_root = Path(args.eval_root)
    results: list[tuple[str, str, dict[str, float | int | str]]] = []
    for language in DEFAULT_LANGUAGE_ORDER:
        option = require_supported_language(language)
        result = evaluate_language(
            index_root / language,
            eval_root / f"{language}_official_validation_1000.jsonl",
            args.queries_per_language,
        )
        results.append((language, option.display_name, result))

    total_queries = sum(int(result["queries_evaluated"]) for _, _, result in results)
    weighted = lambda field: sum(float(result[field]) * int(result["queries_evaluated"]) for _, _, result in results) / total_queries
    lines = [
        "# Multilingual Retrieval Benchmark",
        "",
        "This report benchmarks the completed capped Hindi, Kannada, and Telugu indexes using deterministic queries and selected-passage labels from the official `ai4bharat/MSMARCO-XI` validation files. Each language uses the first 100 evaluable query groups from the same 1,000 source rows used during its index build. Measurements cover retrieval only; they exclude network STT and optional answer generation.",
        "",
        "| Language | Queries | Recall@5 | Recall@10 | MRR | P50 (ms) | P70 (ms) | P100 (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, name, result in results:
        lines.append(
            f"| {name} | {result['queries_evaluated']} | {result['recall_at_5']:.4f} | {result['recall_at_10']:.4f} | {result['mrr']:.4f} | {result['p50']:.3f} | {result['p70']:.3f} | {result['p100']:.3f} |"
        )
    lines.extend([
        "",
        "| Combined weighted quality | Queries | Recall@5 | Recall@10 | MRR |",
        "|---|---:|---:|---:|---:|",
        f"| All three languages | {total_queries} | {weighted('recall_at_5'):.4f} | {weighted('recall_at_10'):.4f} | {weighted('mrr'):.4f} |",
        "",
        "The persisted JSONL evaluation inputs retain original query IDs, translated passages, and official `is_selected` labels, enabling this run to be repeated exactly after any retrieval change.",
    ])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
