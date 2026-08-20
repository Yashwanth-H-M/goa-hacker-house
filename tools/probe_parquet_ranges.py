"""Test authenticated range reads for an official MSMARCO-XI language parquet."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import fsspec
import pyarrow.parquet as pq

from src.config import load_dotenv
from src.languages import require_supported_language


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    option = require_supported_language("kn")
    url = f"https://huggingface.co/datasets/ai4bharat/MSMARCO-XI/resolve/main/{option.validation_parquet}"
    headers = {"Authorization": f"Bearer {os.environ['HF_TOKEN']}"}
    filesystem = fsspec.filesystem("http", headers=headers)
    with filesystem.open(url, "rb", block_size=8 * 1024 * 1024) as source:
        parquet = pq.ParquetFile(source)
        metadata = parquet.metadata
        first_group = parquet.read_row_group(0, columns=["query_id", "passages"])
    print(
        json.dumps(
            {
                "language": option.config,
                "row_groups": metadata.num_row_groups,
                "rows": metadata.num_rows,
                "first_group_rows": first_group.num_rows,
            }
        )
    )


if __name__ == "__main__":
    main()
