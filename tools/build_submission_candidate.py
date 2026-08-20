"""Build a mixed-strategy semantic index from the frozen official validation slice.

The strategy selection follows the local chunking comparison: passage-preserving
Hindi and Kannada indexes prioritize rank/latency, while adaptive semantic
chunking is retained for Telugu where it had the strongest local quality gains.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.chunking import chunk_records
from src.config import DEFAULT_SETTINGS
from src.data import load_jsonl
from src.languages import DEFAULT_LANGUAGE_ORDER, require_supported_language
from src.retrieval import HybridIndex

SELECTED_STRATEGIES = {
    "hi": "passage",
    "kn": "passage",
    "te": "semantic",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-root", default="artifacts/evaluation")
    parser.add_argument("--output-root", default="index/submission_candidate")
    args = parser.parse_args()

    eval_root = Path(args.eval_root)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []

    for language in DEFAULT_LANGUAGE_ORDER:
        option = require_supported_language(language)
        strategy = SELECTED_STRATEGIES[language]
        started = perf_counter()
        records = load_jsonl(eval_root / f"{language}_official_validation_1000.jsonl")
        chunks = chunk_records(records, strategy=strategy, chunk_size=96, chunk_overlap=16)
        index = HybridIndex(
            chunks,
            dimensions=DEFAULT_SETTINGS.embedding_dimensions,
            rrf_k=DEFAULT_SETTINGS.rrf_k,
            semantic_model=DEFAULT_SETTINGS.semantic_model,
        )
        artifact = index.save(output_root / language, strategy=strategy)
        summary = {
            "language": language,
            "display_name": option.display_name,
            "strategy": strategy,
            "records": len(records),
            "chunks": len(chunks),
            "index_artifact": str(artifact),
            "elapsed_ms": round((perf_counter() - started) * 1000, 3),
        }
        summaries.append(summary)
        print(json.dumps(summary, ensure_ascii=False))

    manifest = {
        "dataset": "ai4bharat/MSMARCO-XI",
        "source": "frozen official validation JSONL slice",
        "selection_basis": "artifacts/evaluation/chunking_strategy_comparison.md",
        "semantic_model": DEFAULT_SETTINGS.semantic_model,
        "languages": summaries,
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
