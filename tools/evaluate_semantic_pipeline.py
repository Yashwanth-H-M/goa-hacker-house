"""Evaluate calibrated semantic retrieval against official MSMARCO-XI labels."""

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
from src.pipeline import TextRAGPipeline
from src.retrieval import HybridIndex


def evaluate_language(
    index_dir: Path,
    eval_jsonl: Path,
    max_queries: int,
    minimum_semantic_similarity: float,
    minimum_semantic_margin: float,
) -> dict[str, float | int]:
    index = HybridIndex.load(index_dir)
    pipeline = TextRAGPipeline(
        index,
        minimum_semantic_similarity=minimum_semantic_similarity,
        minimum_semantic_margin=minimum_semantic_margin,
    )
    grouped: dict[str, list] = defaultdict(list)
    for record in load_jsonl(eval_jsonl):
        grouped[record.query_id].append(record)

    recall_at_5: list[float] = []
    recall_at_10: list[float] = []
    reciprocal_rank: list[float] = []
    latency_ms: list[float] = []
    refusals = 0

    for group in grouped.values():
        query = next((record.query for record in group if record.query), None)
        relevant_ids = {record.passage_id for record in group if record.selected is True}
        if not query or not relevant_ids:
            continue
        start = perf_counter()
        response = pipeline.query(query, top_k=10, generate=False)
        latency_ms.append((perf_counter() - start) * 1000)
        returned_parents = [str(item["parent_passage_id"]) for item in response.retrieved_context]
        refusals += int(response.refused)
        recall_at_5.append(float(bool(set(returned_parents[:5]) & relevant_ids)))
        recall_at_10.append(float(bool(set(returned_parents[:10]) & relevant_ids)))
        first_relevant_rank = next(
            (rank for rank, passage_id in enumerate(returned_parents, start=1) if passage_id in relevant_ids),
            None,
        )
        reciprocal_rank.append(1.0 / first_relevant_rank if first_relevant_rank else 0.0)
        if len(latency_ms) >= max_queries:
            break

    evaluated = len(latency_ms)
    if not evaluated:
        raise ValueError("No evaluable official-labeled query groups were found.")
    return {
        "queries_evaluated": evaluated,
        "recall_at_5": sum(recall_at_5) / evaluated,
        "recall_at_10": sum(recall_at_10) / evaluated,
        "mrr": sum(reciprocal_rank) / evaluated,
        "refusal_rate": refusals / evaluated,
        "p50": median(latency_ms),
        "p70": percentile(latency_ms, 70),
        "p100": max(latency_ms),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-root", default="index/semantic_multilingual")
    parser.add_argument("--eval-root", default="artifacts/evaluation")
    parser.add_argument("--queries-per-language", type=int, default=50)
    parser.add_argument("--minimum-semantic-similarity", type=float, default=0.45)
    parser.add_argument("--minimum-semantic-margin", type=float, default=0.015)
    parser.add_argument("--output", default="artifacts/evaluation/semantic_pipeline_benchmark.md")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.queries_per_language < 1:
        raise ValueError("--queries-per-language must be at least 1.")
    if not -1.0 <= args.minimum_semantic_similarity <= 1.0:
        raise ValueError("--minimum-semantic-similarity must be between -1 and 1.")
    if args.minimum_semantic_margin < 0.0:
        raise ValueError("--minimum-semantic-margin must be non-negative.")

    index_root = Path(args.index_root)
    eval_root = Path(args.eval_root)
    results: list[tuple[str, str, dict[str, float | int]]] = []
    for language in DEFAULT_LANGUAGE_ORDER:
        option = require_supported_language(language)
        result = evaluate_language(
            index_root / language,
            eval_root / f"{language}_official_validation_1000.jsonl",
            args.queries_per_language,
            args.minimum_semantic_similarity,
            args.minimum_semantic_margin,
        )
        results.append((language, option.display_name, result))

    total = sum(int(result["queries_evaluated"]) for _, _, result in results)
    weighted = lambda field: sum(float(result[field]) * int(result["queries_evaluated"]) for _, _, result in results) / total
    lines = [
        "# Calibrated Semantic Retrieval Benchmark",
        "",
        "This benchmark evaluates the live pipeline behavior after Indic semantic retrieval and evidence gating. It uses official MSMARCO-XI selected-passage labels and the first configured number of evaluable query groups per language.",
        "",
        "| Language | Queries | Recall@5 | Recall@10 | MRR | Refusal rate | P50 (ms) | P70 (ms) | P100 (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, name, result in results:
        lines.append(
            f"| {name} | {result['queries_evaluated']} | {result['recall_at_5']:.4f} | {result['recall_at_10']:.4f} | {result['mrr']:.4f} | {result['refusal_rate']:.4f} | {result['p50']:.3f} | {result['p70']:.3f} | {result['p100']:.3f} |"
        )
    lines.extend([
        "",
        "| Combined weighted quality | Queries | Recall@5 | Recall@10 | MRR | Refusal rate |",
        "|---|---:|---:|---:|---:|---:|",
        f"| All three languages | {total} | {weighted('recall_at_5'):.4f} | {weighted('recall_at_10'):.4f} | {weighted('mrr'):.4f} | {weighted('refusal_rate'):.4f} |",
        "",
        f"The calibrated semantic-evidence threshold was `{args.minimum_semantic_similarity:.2f}` with a top-candidate score margin of `{args.minimum_semantic_margin:.3f}`.",
    ])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
