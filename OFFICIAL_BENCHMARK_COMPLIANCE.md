# Official Competition Benchmark — E5 Promotion Result

**Date:** 20 August 2026
**Selected model:** `intfloat/multilingual-e5-small`
**Official command:** `.\.venv\Scripts\python.exe -m app.benchmark 50`

## Outcome

The lightweight E5 configuration has been **promoted to the active local application**. It replaced the active Vyakyarth semantic indexes only after retrieval quality and the exact supplied official benchmark were evaluated. The original 270M Vyakyarth indexes have been retained under `index/semantic_multilingual_vyakyarth_270m_backup_20260820` for rollback.

> The official benchmark now passes repeatedly against the E5 Hindi index. This is valid evidence for the benchmark’s warmed, retrieval-only contract; it is not evidence of full microphone-to-answer latency.

| Official E5 run | Embedding P95 (ms) | Search P95 (ms) | Total P95 (ms) | Result |
|---|---:|---:|---:|---|
| Run 1 | 19.35 | 18.40 | 36.11 | Pass |
| Run 2 | 15.76 | 16.58 | 31.55 | Pass |
| Run 3 | 19.86 | 20.51 | 39.59 | Pass |

All three runs used the exact supplied official benchmark source through its documented module path, ran 50 queries after its own warm-up step, preserved the official 50 ms latency budget, and exited with code `0`. Captured outputs are stored in `artifacts/evaluation/official_benchmark_e5_run1.txt`, `official_benchmark_e5_run2.txt`, and `official_benchmark_e5_run3.txt`.

## Why this model was selected

The current Vyakyarth model is documented as a 270M-parameter Indic encoder that explicitly supports Hindi, Kannada, and Telugu. A proposed 0.6B encoder would have been larger and was not assumed to improve CPU latency. The selected E5 model is approximately 0.1B parameters, has 12 layers and 384-dimensional embeddings, and documents support for 94 languages. It also requires asymmetric `query: ` and `passage: ` prefixes for retrieval; the production retriever was updated to apply those prefixes only when the selected semantic model is multilingual E5.[1] [2]

| Configuration | Parameter scale | Embedding dimensions | Retrieval treatment |
|---|---:|---:|---|
| Previous active configuration | 270M | 768 | Vyakyarth semantic vectors plus hashing-vector and BM25 reciprocal-rank fusion |
| Promoted configuration | approximately 0.1B | 384 | E5 semantic vectors with required prefixes, plus the same hashing-vector and BM25 reciprocal-rank fusion |

## Quality comparison

The E5 indexes were built from the same frozen `ai4bharat/MSMARCO-XI` validation records, with the same sentence-chunking setup used for the comparison. The table reports 100 deterministic evaluable queries per language. Quality improved across all three evaluated language routes.

| Language | Recall@5: Vyakyarth → E5 | Recall@10: Vyakyarth → E5 | MRR: Vyakyarth → E5 |
|---|---:|---:|---:|
| Hindi | 0.5700 → 0.6000 | 0.6700 → 0.7500 | 0.3269 → 0.3955 |
| Kannada | 0.3400 → 0.4300 | 0.4300 → 0.5900 | 0.2141 → 0.2673 |
| Telugu | 0.3200 → 0.5300 | 0.5300 → 0.7000 | 0.2179 → 0.3114 |
| Combined weighted result | 0.4100 → 0.5200 | 0.5433 → 0.6800 | 0.2530 → 0.3247 |

The comparison reports are `artifacts/evaluation/semantic_multilingual_benchmark_optimized.md` and `artifacts/evaluation/e5_small_multilingual_quality.md`.

## Live application validation

The restarted local service reports healthy status with all three active E5 indexes available: Hindi has 11,240 chunks, Kannada 10,177, and Telugu 10,237. The 12-test regression suite passed after the promotion.

| Live text API diagnostic, 30 queries per language | Hindi retrieval P50 / P70 / P100 (ms) | Kannada retrieval P50 / P70 / P100 (ms) | Telugu retrieval P50 / P70 / P100 (ms) |
|---|---:|---:|---:|
| Active E5 service | 39.460 / 42.657 / 63.554 | 63.910 / 73.711 / 99.059 | 68.809 / 83.194 / 118.074 |

The live API table is a broader multilingual diagnostic and differs from the official benchmark: it includes local HTTP handling and uses native evaluation queries for each language. It remains **retrieval-path only** and excludes browser audio capture, speech-to-text, and answer generation.

## Active configuration

| Location | Active state |
|---|---|
| `src/config.py` | Default semantic model is `intfloat/multilingual-e5-small`. |
| `src/retrieval.py` | Applies `query: ` and `passage: ` formatting for multilingual E5, while leaving other models unchanged. |
| `index/semantic_multilingual/` | Active E5 Hindi, Kannada, and Telugu semantic indexes. |
| `app/benchmark.py` | Exact supplied official benchmark source, available through `python -m app.benchmark 50`. |
| `app/retriever.py` | Official-benchmark adapter over the production hybrid retriever. |

## Rollback procedure

If a production-quality regression is observed, stop the local service, rename the active E5 directory, and restore the retained Vyakyarth backup. Set `RAG_SEMANTIC_MODEL=krutrim-ai-labs/Vyakyarth` for the rollback service process, or restore that default in `src/config.py`, then restart the service with the restored `index/semantic_multilingual` directory. Re-run the regression tests, health check, and exact official benchmark before reporting the rollback state.

The promotion should not be reverted merely because the multilingual live API values for Kannada or Telugu are above 50 ms: the official benchmark target is a separate warmed benchmark contract, and both the quality comparison and exact official benchmark favor the E5 configuration. Any future end-to-end voice latency claim still requires a dedicated microphone, STT, retrieval, and generation measurement.

## References

[1]: https://huggingface.co/intfloat/multilingual-e5-small "Multilingual E5 Small model card"
[2]: https://ai-labs.olakrutrim.com/models/Vyakyarth-1-Indic-Embedding "Vyakyarth-1-Indic-Embedding model page"
