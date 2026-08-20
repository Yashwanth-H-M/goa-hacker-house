"""Inspect one streamed MSMARCO-XI language parquet without saving corpus rows."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from datasets import load_dataset
from src.config import load_dotenv


def describe(value: object) -> object:
    if isinstance(value, dict):
        return {key: describe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [describe(value[0])] if value else []
    return type(value).__name__


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    source = "hf://datasets/ai4bharat/MSMARCO-XI/validation/hinval.parquet"
    dataset = load_dataset(
        "parquet",
        data_files={"validation": source},
        split="validation",
        streaming=True,
        token=os.getenv("HF_TOKEN") or None,
    )
    first_row = next(iter(dataset))
    print(json.dumps({"source": source, "schema_shape": describe(dict(first_row))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
