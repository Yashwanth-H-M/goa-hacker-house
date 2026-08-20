# Multilingual Retrieval Benchmark

This report benchmarks the completed capped Hindi, Kannada, and Telugu indexes using deterministic queries and selected-passage labels from the official `ai4bharat/MSMARCO-XI` validation files. Each language uses the first 100 evaluable query groups from the same 1,000 source rows used during its index build. Measurements cover retrieval only; they exclude network STT and optional answer generation.

| Language | Queries | Recall@5 | Recall@10 | MRR | P50 (ms) | P70 (ms) | P100 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hindi | 100 | 0.6000 | 0.7500 | 0.3955 | 40.187 | 43.421 | 20702.244 |
| Kannada | 100 | 0.4300 | 0.5900 | 0.2673 | 66.360 | 73.923 | 110.961 |
| Telugu | 100 | 0.5300 | 0.7000 | 0.3114 | 61.172 | 70.803 | 115.315 |

| Combined weighted quality | Queries | Recall@5 | Recall@10 | MRR |
|---|---:|---:|---:|---:|
| All three languages | 300 | 0.5200 | 0.6800 | 0.3247 |

The persisted JSONL evaluation inputs retain original query IDs, translated passages, and official `is_selected` labels, enabling this run to be repeated exactly after any retrieval change.
