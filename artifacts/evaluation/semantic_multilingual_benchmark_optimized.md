# Multilingual Retrieval Benchmark

This report benchmarks the completed capped Hindi, Kannada, and Telugu indexes using deterministic queries and selected-passage labels from the official `ai4bharat/MSMARCO-XI` validation files. Each language uses the first 100 evaluable query groups from the same 1,000 source rows used during its index build. Measurements cover retrieval only; they exclude network STT and optional answer generation.

| Language | Queries | Recall@5 | Recall@10 | MRR | P50 (ms) | P70 (ms) | P100 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hindi | 100 | 0.5700 | 0.6700 | 0.3269 | 62.977 | 68.739 | 19677.493 |
| Kannada | 100 | 0.3400 | 0.4300 | 0.2141 | 91.202 | 102.664 | 10669.984 |
| Telugu | 100 | 0.3200 | 0.5300 | 0.2179 | 80.840 | 90.943 | 10868.866 |

| Combined weighted quality | Queries | Recall@5 | Recall@10 | MRR |
|---|---:|---:|---:|---:|
| All three languages | 300 | 0.4100 | 0.5433 | 0.2530 |

The persisted JSONL evaluation inputs retain original query IDs, translated passages, and official `is_selected` labels, enabling this run to be repeated exactly after any retrieval change.
