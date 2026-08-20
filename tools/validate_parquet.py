"""Validate an already-downloaded official MSMARCO-XI parquet file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pyarrow.parquet as pq


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    args = parser.parse_args()
    source = Path(args.path)
    parquet = pq.ParquetFile(source)
    metadata = parquet.metadata
    first_batch = next(parquet.iter_batches(batch_size=1, columns=["query_id", "passages"]))
    if first_batch.num_rows != 1:
        raise ValueError("The parquet file did not return its first expected record.")
    print(
        json.dumps(
            {
                "path": str(source),
                "bytes": source.stat().st_size,
                "rows": metadata.num_rows,
                "row_groups": metadata.num_row_groups,
                "validation": "passed",
            }
        )
    )


if __name__ == "__main__":
    main()
