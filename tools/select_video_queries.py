"""Select evidence-backed demonstration queries from official validation records.

This utility only calls the local Contextline API with generation disabled. It ranks
queries by successful response, evidence count, and confidence so the resulting
query sheet is suitable for a reliable screen-recorded demonstration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib import request


LANGUAGES = ("hi", "kn", "te")


def post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with request.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def unique_queries(path: Path, limit: int) -> list[str]:
    seen: set[str] = set()
    queries: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        value = record.get("query")
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        queries.append(text)
        if len(queries) >= limit:
            break
    return queries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--eval-root", default="artifacts/evaluation")
    parser.add_argument("--scan-per-language", type=int, default=40)
    parser.add_argument("--take", type=int, default=3)
    parser.add_argument("--output", default="artifacts/evaluation/video_demo_query_candidates.json")
    args = parser.parse_args()

    report: dict[str, list[dict[str, object]]] = {}
    for language in LANGUAGES:
        candidates: list[dict[str, object]] = []
        source = Path(args.eval_root) / f"{language}_official_validation_1000.jsonl"
        for question in unique_queries(source, args.scan_per_language):
            response = post_json(
                f"{args.base_url.rstrip('/')}/api/query",
                {"question": question, "language": language, "generate": False, "top_k": 5},
            )
            refused = bool(response.get("refused"))
            contexts = response.get("retrieved_context", [])
            context_count = len(contexts) if isinstance(contexts, list) else 0
            confidence = float(response.get("confidence", 0.0))
            if refused or context_count == 0:
                continue
            candidates.append(
                {
                    "question": question,
                    "confidence": round(confidence, 4),
                    "cited_chunks": len(response.get("cited_chunk_ids", [])),
                    "context_items": context_count,
                    "path_taken": response.get("path_taken"),
                    "api_end_to_end_ms": response.get("latency_ms", {}).get("api_end_to_end"),
                }
            )
        candidates.sort(
            key=lambda item: (
                int(item["context_items"]),
                int(item["cited_chunks"]),
                float(item["confidence"]),
            ),
            reverse=True,
        )
        report[language] = candidates[: args.take]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
