# Live Text API Latency Benchmark

The local server was measured with official MSMARCO-XI validation queries using text requests with `generate=false`. These are retrieval-path diagnostics only: they exclude browser audio capture, network speech-to-text, and answer generation. They must not be represented as full voice-to-answer latency.

| Language | Queries | Client wall P50/P70/P100 (ms) | Server API P50/P70/P100 (ms) | Retrieval P50/P70/P100 (ms) |
|---|---:|---:|---:|---:|
| Hindi | 30 | 41.666 / 44.311 / 110.073 | 39.553 / 42.742 / 63.669 | 39.460 / 42.657 / 63.554 |
| Kannada | 30 | 67.269 / 78.040 / 101.279 | 64.011 / 73.820 / 99.186 | 63.910 / 73.711 / 99.059 |
| Telugu | 30 | 73.018 / 88.732 / 122.231 | 68.960 / 83.294 / 118.176 | 68.809 / 83.194 / 118.074 |
