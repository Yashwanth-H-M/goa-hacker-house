"""Create a labeled retrieval evaluation set from an official MSMARCO-XI slice.

The resulting JSONL contains the same normalized records used by the bounded
multilingual index build, including official selected-passage labels.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data import load_msmarco_xi, write_jsonl
from src.languages import require_supported_language


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", required=True, help="Configured language code: hi, kn, or te.")
    parser.add_argument("--rows", type=int, default=1000, help="Official validation rows to normalize.")
    parser.add_argument("--output", required=True, help="Target JSONL path.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.rows < 1:
        raise ValueError("--rows must be at least 1.")

    option = require_supported_language(args.language)
    records = load_msmarco_xi(language=option.config, split="validation", limit=args.rows)
    labeled_queries = {record.query_id for record in records if record.selected is True and record.query}
    if not labeled_queries:
        raise ValueError("The requested official-corpus slice has no selected relevance labels.")

    output = Path(args.output)
    write_jsonl(records, output)
    print(
        f"Wrote {len(records)} normalized passages for {len(labeled_queries)} labeled "
        f"{option.display_name} queries to {output}."
    )


if __name__ == "__main__":
    main()
