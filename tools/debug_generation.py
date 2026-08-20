"""Run a local, sanitized diagnostic for the grounded-generation adapter."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DEFAULT_SETTINGS
from src.providers import OpenAICompatibleGenerator
from src.retrieval import HybridIndex


def main() -> None:
    index = HybridIndex.load(Path("index/dev"))
    generator = OpenAICompatibleGenerator(
        api_key=DEFAULT_SETTINGS.openai_api_key,
        base_url=DEFAULT_SETTINGS.openai_base_url,
        model=DEFAULT_SETTINGS.openai_model,
    )
    try:
        answer = generator.generate("What is BM25?", index.search("What is BM25?", top_k=3))
        print("STATUS=complete")
        print(f"CITATION_COUNT={len(answer.cited_chunk_ids)}")
    except Exception as exc:  # The message excludes request headers and secrets.
        print(f"ERROR_TYPE={type(exc).__name__}")
        print(f"ERROR_MESSAGE={str(exc)[:1000]}")


if __name__ == "__main__":
    main()
