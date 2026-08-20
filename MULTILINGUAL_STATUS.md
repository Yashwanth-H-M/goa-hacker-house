# Multilingual Implementation Status

**Scope:** Hindi (`hi`), Kannada (`kn`), and Telugu (`te`) voice-enabled retrieval over the official `ai4bharat/MSMARCO-XI` validation corpus.[1]

> **Current state:** All three language indexes are complete, the local browser/API interface discovers each index, and retrieval has been evaluated against official selected-passage labels. The optional answer-generation provider is configured but currently cannot generate answers because its account has no usable quota; the application therefore fails closed rather than returning uncited text.

## Corpus and Index Completion

Each language index uses the first 1,000 source rows of its official validation parquet. The project flattens translated passages, retains the dataset's `is_selected` relevance labels, applies sentence-aware chunking, and persists an independent hybrid (BM25 + deterministic vector + RRF) index per language.

| Language | Official validation file | Source rows | Normalized passages | Chunks | Index directory |
|---|---|---:|---:|---:|---|
| Hindi | `validation/hinval.parquet` | 1,000 | 9,988 | 11,240 | `index/multilingual/hi/` |
| Kannada | `validation/kanval.parquet` | 1,000 | 9,988 | 10,177 | `index/multilingual/kn/` |
| Telugu | `validation/telval.parquet` | 1,000 | 9,988 | 10,237 | `index/multilingual/te/` |
| **Total** | — | **3,000** | **29,964** | **31,654** | `index/multilingual/` |

The Telugu parquet download completed at the expected **474,142,748 bytes**, and its completed index is now included in `index/multilingual/manifest.json`. The resumable downloader can still be used safely if the corpus files must be recreated:

```powershell
Set-Location 'C:\Users\yashw\Desktop\goa hacker house'
powershell -NoProfile -ExecutionPolicy Bypass -File tools\download_remaining_languages.ps1
```

## Local Application Verification

The application starts with all completed indexes using the following command:

```powershell
Set-Location 'C:\Users\yashw\Desktop\goa hacker house'
.\.venv\Scripts\python.exe -m src.serve --index-dir index\multilingual --port 8000
```

The health endpoint verified all three active language routes and their chunk counts. Retrieval-only `POST /api/query` checks also completed successfully for Hindi, Kannada, and Telugu with generation disabled. The local interface is available at `http://127.0.0.1:8000` while that command is running.

| Provider or route | Verified condition | Result |
|---|---|---|
| Sarvam STT | API credential configured and previously live-validated with a spoken probe | Ready for `hi-IN`, `kn-IN`, and `te-IN` audio requests |
| Text API | One retrieval-only query per language after the final index build | Successful for Hindi, Kannada, and Telugu |
| Browser/API health | `GET /api/health` after final index build | Reports `hi`, `kn`, and `te` |
| Grounded generation | OpenAI-compatible provider configured | Fail-closed when quota is unavailable; no unsupported answer is emitted |
| Unit tests | `python -m unittest discover -s tests -p 'test_*.py' -v` | 8 tests passed |

## Official-Corpus Retrieval Benchmark

The benchmark is reproducible from saved official-corpus JSONL records in `artifacts/evaluation/`. It uses the first **100 evaluable query groups per language** from the same bounded 1,000-row corpus slices used by the corresponding indexes. Scores measure retrieval only, excluding network speech-to-text and optional answer generation.

| Language | Queries | Recall@5 | Recall@10 | MRR | P50 (ms) | P70 (ms) | P100 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hindi | 100 | 0.3600 | 0.5200 | 0.2630 | 318.618 | 332.051 | 378.879 |
| Kannada | 100 | 0.2700 | 0.3300 | 0.1766 | 378.209 | 404.952 | 520.772 |
| Telugu | 100 | 0.2500 | 0.3500 | 0.1476 | 387.869 | 410.609 | 565.067 |
| **All three languages (weighted)** | **300** | **0.2933** | **0.4000** | **0.1957** | — | — | — |

Run the same benchmark again after any retrieval modification:

```powershell
Set-Location 'C:\Users\yashw\Desktop\goa hacker house'
.\.venv\Scripts\python.exe tools\run_multilingual_benchmark.py `
  --index-root index\multilingual `
  --eval-root artifacts\evaluation `
  --queries-per-language 100 `
  --output artifacts\evaluation\multilingual_benchmark.md
```

## Remaining Submission Work

The local multilingual implementation is complete, but the competition submission is not yet ready to submit. It still requires a public deployment, a GitHub repository, the mandated demonstration/process videos, and the required social-media promotion. Answer generation also needs an account with usable quota or an approved OpenAI-compatible provider; until then, the present fail-closed behavior is the intended safety measure.

### References

[1]: https://huggingface.co/datasets/ai4bharat/MSMARCO-XI "ai4bharat/MSMARCO-XI on Hugging Face"
