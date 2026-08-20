"""Query a built local hybrid-retrieval index."""

from __future__ import annotations

import argparse
import json

from src.config import DEFAULT_SETTINGS
from src.pipeline import TextRAGPipeline
from src.providers import OpenAICompatibleGenerator
from src.retrieval import HybridIndex


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", required=True)
    parser.add_argument("--text", required=True, help="Text input; audio input is available through src.serve.")
    parser.add_argument("--top-k", type=int, default=DEFAULT_SETTINGS.default_top_k)
    parser.add_argument("--minimum-similarity", type=float, default=DEFAULT_SETTINGS.minimum_similarity)
    parser.add_argument("--generate", action="store_true", help="Request an OpenAI-compatible grounded answer when OPENAI_API_KEY is configured.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    index = HybridIndex.load(args.index_dir)
    generator = OpenAICompatibleGenerator(
        api_key=DEFAULT_SETTINGS.openai_api_key,
        base_url=DEFAULT_SETTINGS.openai_base_url,
        model=DEFAULT_SETTINGS.openai_model,
    )
    pipeline = TextRAGPipeline(index, minimum_similarity=args.minimum_similarity, generator=generator)
    response = pipeline.query(args.text, top_k=args.top_k, generate=args.generate)
    print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
