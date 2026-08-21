# Benchmark Verification Report

**Reviewed:** 20 August 2026
**Supplied file:** `benchmark(1).py`
**Project tested:** Contextline — HH Goa Voice RAG

## Verdict

The supplied script is a reasonable **starting template for a steady-state microbenchmark**, but it is **not usable as-is for this project and is not sufficient as final benchmark evidence**. Its assumptions describe a different application: it imports `app.config` and `app.retriever`, expects a `LATENCY_BUDGET_MS` constant, and is labelled as an embedding-plus-FAISS benchmark. The current project has no `app/` package, no `LATENCY_BUDGET_MS` setting, and no FAISS index.

An unchanged compatibility run was attempted with the project virtual environment and failed before measurement:

```text
ModuleNotFoundError: No module named 'app'
```

The project instead uses `src.retrieval.HybridIndex`, which combines a hashing-vector dense channel, BM25 sparse retrieval, optional semantic vectors, and reciprocal-rank fusion. The current live benchmark therefore measures the running service through its real `/api/query` route instead of pretending to use a missing FAISS retriever.

## Exact supplied-script check

| Check | Result | Interpretation |
|---|---|---|
| Imports `app.config` | Failed | This project uses `src.config`; no `app` package exists. |
| Imports `app.retriever` | Failed | This project uses `src.retrieval.HybridIndex`; its interface differs. |
| Reads `LATENCY_BUDGET_MS` | Not available | `src.config.Settings` has no latency-budget field. |
| Measures FAISS search | Not applicable | The current project does not use FAISS. |
| Executes unmodified | Failed before warm-up | The script cannot produce a valid number for this application. |

## Methodology assessment

The supplied script has useful properties. It warms the model once before timing, reports mean and percentile values, runs a configurable number of iterations, and returns a non-zero status when its assumed threshold is exceeded. These are appropriate ideas for a **steady-state** latency test.

However, the evidence would be too weak for a deployment or competition claim even if the imports matched. The default sample has only 50 requests drawn cyclically from eight English technical prompts. That is too small and too repetitive for a stable P99 estimate, does not reflect the project’s Hindi, Kannada, and Telugu corpus routes, and does not record raw observations for audit. It also does not test source relevance, error handling, concurrency, cold start separately, API overhead, microphone capture, speech-to-text, or answer generation.

| Methodological requirement | Supplied script | Required improvement |
|---|---|---|
| Correct production code path | No | Benchmark `src.retrieval.HybridIndex` or the real local API. |
| Corpus-representative queries | No | Use saved official validation queries for Hindi, Kannada, and Telugu. |
| Multilingual reporting | No | Report each enabled language separately. |
| Raw audit trail | No | Save individual request timings and run configuration as CSV or JSON. |
| P95/P99 stability | Weak at 50 repeated requests | Increase sample size and use multiple runs; report repeatability. |
| Cold-start behaviour | Excluded but not labelled | Report a separate startup/warm-up measurement. |
| End-to-end voice performance | No | Run an actual browser microphone capture with STT and optional generation, labelled separately. |
| Correctness alongside speed | No | Include retrieval quality, refusal behaviour, and provider failures. |

## Project-compatible live benchmark

A project-compatible benchmark was run against the active local service with **50 official validation queries per language** and `generate=false`. This is a 150-request text-API benchmark. It measures the request-to-response path, including live local retrieval, after the service has already started and warmed the semantic encoder.

> These values are **not full voice-to-answer latency**. They exclude browser audio capture, remote speech-to-text, and answer generation. They must not be used to claim an end-to-end voice latency result.

| Language | Client wall P50 / P70 / P100 (ms) | Server API P50 / P70 / P100 (ms) | Retrieval P50 / P70 / P100 (ms) |
|---|---:|---:|---:|
| Hindi | 62.538 / 66.163 / 155.720 | 60.611 / 64.055 / 90.748 | 60.507 / 63.952 / 90.645 |
| Kannada | 89.689 / 98.092 / 150.656 | 87.556 / 96.044 / 148.492 | 87.414 / 95.945 / 148.362 |
| Telugu | 93.881 / 103.902 / 147.655 | 91.922 / 101.760 / 145.606 | 91.809 / 101.631 / 145.475 |

The underlying report is `artifacts/evaluation/live_text_api_benchmark_50.md`. If a 50 ms retrieval SLO were imposed externally, this run would not meet it: every language’s retrieval P50 exceeded 50 ms. That comparison is illustrative only because the current project does not define a `LATENCY_BUDGET_MS` threshold.

## Recommendation

Keep the uploaded script as a reference example, but do not use it in the final submission without rewriting it for the current implementation. The existing `tools/benchmark_api_text.py` is the correct short-term benchmark because it uses the real running server and official validation data. The next improvement should add P95 and P99, persist raw timing samples and environment metadata, and run separate controlled benchmarks for cold start, steady-state retrieval, real microphone-to-response flow, and generated-answer flow.

The benchmark is therefore **not up to the required standard as supplied**, while the project-compatible live API benchmark is a valid and honest retrieval-path diagnostic.
