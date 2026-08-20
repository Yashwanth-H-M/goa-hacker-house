"""Build comparable multilingual semantic indexes for model-selection experiments.

The tool preserves the existing normalized official-validation records and
chunking strategy while changing only the semantic embedding model. It is used
to compare quality and official benchmark latency without overwriting the active
Vyakyarth-based index.
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Sentence-transformers model identifier.")
    parser.add_argument("--output-root", required=True, help="Directory for generated language indexes.")
    parser.add_argument("--eval-root", default="artifacts/evaluation")
    parser.add_argument("--strategy", default="sentence", choices=("fixed", "fixed_overlap", "sentence", "semantic", "passage"))
    parser.add_argument("--languages", nargs="+", default=list(DEFAULT_LANGUAGE_ORDER), choices=DEFAULT_LANGUAGE_ORDER)
    parser.add_argument("--chunk-size", type=int, default=96)
    parser.add_argument("--chunk-overlap", type=int, default=16)
    return parser


def main() -> None:
    arguments = build_parser().parse_args()
    if arguments.chunk_size < 1:
        raise ValueError("--chunk-size must be positive.")
    if arguments.chunk_overlap < 0 or arguments.chunk_overlap >= arguments.chunk_size:
        raise ValueError("--chunk-overlap must be non-negative and smaller than --chunk-size.")

    output_root = Path(arguments.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []

    for language in arguments.languages:
        option = require_supported_language(language)
        started = perf_counter()
        records = load_jsonl(Path(arguments.eval_root) / f"{language}_official_validation_1000.jsonl")
        chunks = chunk_records(
            records,
            strategy=arguments.strategy,
            chunk_size=arguments.chunk_size,
            chunk_overlap=arguments.chunk_overlap,
        )
        index = HybridIndex(
            chunks,
            dimensions=DEFAULT_SETTINGS.embedding_dimensions,
            rrf_k=DEFAULT_SETTINGS.rrf_k,
            semantic_model=arguments.model,
        )
        artifact = index.save(output_root / language, strategy=arguments.strategy)
        summary = {
            "language": language,
            "display_name": option.display_name,
            "records": len(records),
            "chunks": len(chunks),
            "strategy": arguments.strategy,
            "semantic_model": arguments.model,
            "index_artifact": str(artifact),
            "elapsed_ms": round((perf_counter() - started) * 1000, 3),
        }
        summaries.append(summary)
        print(json.dumps(summary, ensure_ascii=False))

    manifest = {
        "dataset": "ai4bharat/MSMARCO-XI",
        "source": "frozen official validation JSONL slice",
        "semantic_model": arguments.model,
        "strategy": arguments.strategy,
        "languages": summaries,
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
