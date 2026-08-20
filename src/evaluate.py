"""Evaluate retrieval quality and retrieval-only latency against normalized labeled records."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from src.data import load_jsonl
from src.retrieval import HybridIndex


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((percent / 100) * len(ordered)) - 1))
    return ordered[index]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", required=True)
    parser.add_argument("--eval-jsonl", required=True, help="Normalized records with query and selected relevance labels.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    index = HybridIndex.load(args.index_dir)
    records = load_jsonl(args.eval_jsonl)

    grouped: dict[str, list] = defaultdict(list)
    for record in records:
        grouped[record.query_id].append(record)

    recalls_at_5: list[float] = []
    recalls_at_10: list[float] = []
    reciprocal_ranks: list[float] = []
    retrieval_latencies: list[float] = []

    for query_id, group in grouped.items():
        query = next((record.query for record in group if record.query), None)
        relevant_ids = {record.passage_id for record in group if record.selected is True}
        if not query or not relevant_ids:
            continue

        start = perf_counter()
        results = index.search(query, top_k=max(args.top_k, 10))
        retrieval_latencies.append((perf_counter() - start) * 1000)
        returned_parents = [result.chunk.parent_passage_id for result in results]

        recalls_at_5.append(float(bool(set(returned_parents[:5]) & relevant_ids)))
        recalls_at_10.append(float(bool(set(returned_parents[:10]) & relevant_ids)))
        first_relevant_rank = next((rank for rank, passage_id in enumerate(returned_parents, start=1) if passage_id in relevant_ids), None)
        reciprocal_ranks.append(1.0 / first_relevant_rank if first_relevant_rank else 0.0)

    evaluated = len(recalls_at_5)
    if not evaluated:
        raise ValueError("No evaluable query groups found; records need query text and selected=True labels.")

    result = {
        "queries_evaluated": evaluated,
        "recall_at_5": sum(recalls_at_5) / evaluated,
        "recall_at_10": sum(recalls_at_10) / evaluated,
        "mrr": sum(reciprocal_ranks) / evaluated,
        "latency_ms": {
            "p50": median(retrieval_latencies),
            "p70": percentile(retrieval_latencies, 70),
            "p100": max(retrieval_latencies),
        },
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "# Retrieval Evaluation\n\n"
        f"Queries evaluated: **{result['queries_evaluated']}**\n\n"
        "| Recall@5 | Recall@10 | MRR | Retrieval P50 (ms) | P70 (ms) | P100 (ms) |\n"
        "|---:|---:|---:|---:|---:|---:|\n"
        f"| {result['recall_at_5']:.4f} | {result['recall_at_10']:.4f} | {result['mrr']:.4f} | "
        f"{result['latency_ms']['p50']:.3f} | {result['latency_ms']['p70']:.3f} | {result['latency_ms']['p100']:.3f} |\n\n"
        "This baseline evaluates hybrid retrieval only. Report full-pipeline latency separately once STT and generation are enabled.\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
