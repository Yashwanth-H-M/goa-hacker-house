# Chunking Strategy Comparison

This reproducible development benchmark compares five provenance-preserving chunking strategies over the saved official `ai4bharat/MSMARCO-XI` validation records. Each strategy is measured with the same 100 evaluable query groups per language and deterministic hybrid retrieval (hashing-vector dense retrieval + BM25 + RRF). It deliberately excludes remote semantic embedding, STT, and answer generation so the table isolates chunking and local retrieval effects.

| Language | Strategy | Chunks | Build (ms) | Queries | Recall@5 | Recall@10 | MRR | P50 retrieval (ms) | P70 retrieval (ms) | P100 retrieval (ms) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Hindi | fixed | 11227 | 1761.491 | 100 | 0.3500 | 0.5300 | 0.2538 | 13.229 | 14.677 | 40.416 |
| Hindi | fixed_overlap | 12026 | 3725.199 | 100 | 0.3400 | 0.5200 | 0.2536 | 24.917 | 28.862 | 48.344 |
| Hindi | sentence | 11240 | 3326.855 | 100 | 0.3600 | 0.5200 | 0.2632 | 23.899 | 27.453 | 41.891 |
| Hindi | semantic | 19134 | 3069.720 | 100 | 0.3800 | 0.4800 | 0.2407 | 22.013 | 23.291 | 31.491 |
| Hindi | passage | 9988 | 2699.233 | 100 | 0.3600 | 0.5800 | 0.2729 | 24.431 | 26.753 | 38.500 |
| Kannada | fixed | 10159 | 3520.440 | 100 | 0.2700 | 0.3300 | 0.1782 | 55.918 | 66.313 | 120.773 |
| Kannada | fixed_overlap | 10389 | 3454.914 | 100 | 0.2600 | 0.3300 | 0.1761 | 57.278 | 65.592 | 127.496 |
| Kannada | sentence | 10177 | 3464.790 | 100 | 0.2700 | 0.3300 | 0.1766 | 46.150 | 55.029 | 106.692 |
| Kannada | semantic | 12241 | 3457.817 | 100 | 0.2800 | 0.3200 | 0.1775 | 52.969 | 62.092 | 105.173 |
| Kannada | passage | 9988 | 2795.451 | 100 | 0.2700 | 0.3300 | 0.1781 | 45.056 | 51.852 | 92.795 |
| Telugu | fixed | 10222 | 3095.008 | 100 | 0.2500 | 0.3500 | 0.1442 | 46.077 | 57.761 | 111.552 |
| Telugu | fixed_overlap | 10527 | 2623.600 | 100 | 0.2600 | 0.3400 | 0.1467 | 43.243 | 52.872 | 97.481 |
| Telugu | sentence | 10237 | 2995.942 | 100 | 0.2500 | 0.3500 | 0.1476 | 44.309 | 52.827 | 99.173 |
| Telugu | semantic | 11751 | 4233.531 | 100 | 0.2700 | 0.3300 | 0.1550 | 66.162 | 77.453 | 142.575 |
| Telugu | passage | 9988 | 2832.502 | 100 | 0.2500 | 0.3400 | 0.1473 | 47.106 | 55.903 | 111.625 |

## Interpretation guidance

Select the default strategy from the measured quality/latency trade-off rather than from a conceptual preference. Any production semantic-embedding or generation benchmark must be reported separately because its external-model latency is not represented in this local retrieval-only table.
