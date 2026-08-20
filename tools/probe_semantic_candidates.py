"""Inspect top semantic candidates independently of RRF for threshold calibration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import _evidence_terms
from src.retrieval import HybridIndex


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    index = HybridIndex.load(args.index_dir)
    if not index.semantic_enabled:
        raise ValueError("The selected index does not contain semantic vectors.")
    query_vector = index._encode_semantic_query(args.query)
    scores = (index.semantic_vectors @ query_vector).tolist()
    query_terms = _evidence_terms(args.query)
    ranked = sorted(range(len(scores)), key=lambda item: -scores[item])[: args.top_k]
    output = []
    for rank, position in enumerate(ranked, start=1):
        chunk = index.chunks[position]
        output.append(
            {
                "rank": rank,
                "semantic_score": round(scores[position], 8),
                "chunk_id": chunk.chunk_id,
                "selected": chunk.selected,
                "shared_content_terms": sorted(query_terms.intersection(_evidence_terms(chunk.text))),
                "text": chunk.text,
            }
        )
    print(json.dumps({"query": args.query, "query_terms": sorted(query_terms), "candidates": output}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
