"""Measure live text-query API latency using official MSMARCO-XI validation queries.

This benchmark measures the running server's request-to-response timing for
retrieval-only requests. Network speech-to-text, browser audio capture, and
answer generation are disabled; results must not be represented as full
voice-to-answer latency.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter
from urllib import request

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data import load_jsonl
from src.evaluate import percentile
from src.languages import DEFAULT_LANGUAGE_ORDER, require_supported_language


def post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    """Send one local JSON request and return the parsed response."""

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with request.urlopen(http_request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def _triplet(values: list[float]) -> tuple[float, float, float]:
    return median(values), percentile(values, 70), max(values)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--eval-root", default="artifacts/evaluation")
    parser.add_argument("--queries-per-language", type=int, default=30)
    parser.add_argument("--output", default="artifacts/evaluation/live_text_api_benchmark.md")
    args = parser.parse_args()
    if args.queries_per_language < 1:
        raise ValueError("--queries-per-language must be at least 1.")

    results: list[dict[str, object]] = []
    for language in DEFAULT_LANGUAGE_ORDER:
        option = require_supported_language(language)
        records = load_jsonl(Path(args.eval_root) / f"{language}_official_validation_1000.jsonl")
        grouped: dict[str, list] = defaultdict(list)
        for record in records:
            grouped[record.query_id].append(record)

        wall_ms: list[float] = []
        api_ms: list[float] = []
        retrieval_ms: list[float] = []
        successful = 0
        for group in grouped.values():
            query = next((record.query for record in group if record.query), None)
            if not query:
                continue
            started = perf_counter()
            response = post_json(
                f"{args.base_url.rstrip('/')}/api/query",
                {"question": query, "language": language, "generate": False, "top_k": 5},
            )
            wall_ms.append((perf_counter() - started) * 1000)
            timings = response.get("latency_ms", {})
            if not isinstance(timings, dict):
                raise ValueError("API response omitted latency_ms.")
            api_ms.append(float(timings["api_end_to_end"]))
            retrieval_ms.append(float(timings["retrieval"]))
            successful += 1
            if successful >= args.queries_per_language:
                break

        if not successful:
            raise ValueError(f"No evaluable queries found for {language}.")
        wall_p50, wall_p70, wall_p100 = _triplet(wall_ms)
        api_p50, api_p70, api_p100 = _triplet(api_ms)
        retrieval_p50, retrieval_p70, retrieval_p100 = _triplet(retrieval_ms)
        results.append(
            {
                "language": option.display_name,
                "queries": successful,
                "wall_p50": wall_p50,
                "wall_p70": wall_p70,
                "wall_p100": wall_p100,
                "api_p50": api_p50,
                "api_p70": api_p70,
                "api_p100": api_p100,
                "retrieval_p50": retrieval_p50,
                "retrieval_p70": retrieval_p70,
                "retrieval_p100": retrieval_p100,
            }
        )

    lines = [
        "# Live Text API Latency Benchmark",
        "",
        "The local server was measured with official MSMARCO-XI validation queries using text requests with `generate=false`. These are retrieval-path diagnostics only: they exclude browser audio capture, network speech-to-text, and answer generation. They must not be represented as full voice-to-answer latency.",
        "",
        "| Language | Queries | Client wall P50/P70/P100 (ms) | Server API P50/P70/P100 (ms) | Retrieval P50/P70/P100 (ms) |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            "| {language} | {queries} | {wall_p50:.3f} / {wall_p70:.3f} / {wall_p100:.3f} | "
            "{api_p50:.3f} / {api_p70:.3f} / {api_p100:.3f} | "
            "{retrieval_p50:.3f} / {retrieval_p70:.3f} / {retrieval_p100:.3f} |".format(**row)
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
