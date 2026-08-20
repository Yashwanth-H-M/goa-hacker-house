"""Inspect semantic retrieval scores for calibration checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval import HybridIndex


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", required=True)
    parser.add_argument("--query", action="append", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    index = HybridIndex.load(args.index_dir)
    for query in args.query:
        results = index.search(query, top_k=3)
        print(
            json.dumps(
                {
                    "query": query,
                    "semantic_enabled": index.semantic_enabled,
                    "results": [result.to_dict() for result in results],
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
