"""Inspect the live MSMARCO-XI schema without saving corpus content locally."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from datasets import get_dataset_config_names, load_dataset
from src.config import load_dotenv


def describe(value: object) -> object:
    if isinstance(value, dict):
        return {key: describe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [describe(value[0])] if value else []
    return type(value).__name__


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    dataset_name = "ai4bharat/MSMARCO-XI"
    token = os.getenv("HF_TOKEN") or None
    configs = get_dataset_config_names(dataset_name, token=token)
    dataset = load_dataset(dataset_name, split="validation", streaming=True, token=token)
    first_row = next(iter(dataset))
    output = {
        "dataset": dataset_name,
        "configs": configs,
        "top_level_keys": sorted(first_row.keys()),
        "schema_shape": describe(dict(first_row)),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
