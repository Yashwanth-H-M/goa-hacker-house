# Contextline — Multilingual Voice RAG

**Contextline** is a local-first, voice-enabled Retrieval-Augmented Generation (RAG) prototype built for **HH Goa 2026 Shortlisting Task 2**. It supports **Hindi, Kannada, and Telugu** retrieval over the competition-linked `ai4bharat/MSMARCO-XI` corpus, displays retrieved evidence, provides safety-oriented refusals, and can optionally transcribe voice with Sarvam and generate grounded answers through an OpenAI-compatible provider.

> **Current status:** The active `intfloat/multilingual-e5-small` configuration passed the supplied official 50-query retrieval benchmark in repeated runs. This result measures warmed retrieval only; it does **not** represent full microphone-to-answer latency.

## Highlights

| Capability | Implementation |
|---|---|
| Multilingual retrieval | Separate active indexes for Hindi, Kannada, and Telugu. |
| Lightweight semantic model | `intfloat/multilingual-e5-small` with required `query: ` and `passage: ` formatting. |
| Hybrid ranking | Semantic vectors, deterministic hashing-vector similarity, BM25, and Reciprocal Rank Fusion (RRF). |
| Grounding | Retrieved chunks and provenance are returned with each query; answer generation is constrained to retrieved context. |
| Safety-oriented refusal | Early unsafe-input screening and fail-closed behavior when evidence or a provider is unavailable. |
| Voice interaction | Browser audio can be transcribed with Sarvam; grounded answer generation is optional. |
| Evaluation | Saved retrieval-quality reports, live API diagnostics, and a supplied official benchmark adapter. |

## Architecture

```text
Browser UI
    │  typed query or recorded audio
    ▼
Python service (src.serve)
    ├── Sarvam STT, optional
    ├── Hindi / Kannada / Telugu HybridIndex
    │     ├── E5 semantic vectors
    │     ├── hashing-vector channel
    │     ├── BM25 channel
    │     └── RRF fusion
    ├── safety and grounding checks
    └── OpenAI-compatible grounded generation, optional
    ▼
Answer or refusal + retrieved source chunks + timings
```

The current browser interface and API are served by the same Python process. For a public deployment, host this service together rather than exposing provider keys in a static frontend.

## Repository layout

| Path | Purpose |
|---|---|
| `src/` | Application configuration, data handling, hybrid retrieval, guardrails, providers, and the browser/API server. |
| `app/` | Compatibility package for the supplied official benchmark command. |
| `tools/` | Dataset preparation, index building, validation, and benchmark utilities. |
| `tests/` | Deterministic unit tests and a small offline fixture. |
| `artifacts/evaluation/` | Publishable benchmark reports and captured official benchmark output. Raw downloaded validation data is intentionally ignored. |
| `ARCHITECTURE.md` | Detailed component and data-flow documentation. |
| `EVALUATION.md` | Evaluation methodology and evidence boundaries. |
| `GUARDRAILS.md` | Safety and grounded-generation behavior. |
| `OFFICIAL_BENCHMARK_COMPLIANCE.md` | Official benchmark runs, active E5 promotion, and rollback details. |
| `USAGE.md` | Additional local workflow notes. |

## Requirements

Use Python 3.11 or later. The project is developed and tested on Windows PowerShell, but the Python commands are portable with path adjustments.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Install the Hugging Face extras only when downloading official corpus files:

```powershell
python -m pip install -r requirements-hf.txt
```

## Configuration

Copy the template and add real credentials only to the local, git-ignored `.env` file.

```powershell
copy .env.example .env
```

| Variable | Purpose | Required for |
|---|---|---|
| `SARVAM_API_KEY` | Sarvam Speech-to-Text access | Browser voice transcription |
| `SARVAM_STT_MODEL` | Sarvam transcription model selection | Optional; defaults to `saaras:v3` |
| `OPENAI_API_KEY` | OpenAI-compatible grounded-generation access | Generated answers |
| `OPENAI_BASE_URL` | Compatible generation endpoint | Optional; defaults to OpenAI API URL |
| `OPENAI_MODEL` | Generation model name | Optional; defaults to `gpt-4o-mini` |
| `HF_TOKEN` | Hugging Face access for official corpus downloads | Large official dataset downloads |
| `RAG_SEMANTIC_MODEL` | Semantic model override | Optional; defaults to `intfloat/multilingual-e5-small` |

Never commit `.env`, API keys, browser recordings containing private material, or generated index directories.

## Quick offline smoke test

The included fixture exercises the basic retrieval path without downloading the official corpus or configuring providers.

```powershell
.\.venv\Scripts\python.exe -m src.ingest `
  --source-jsonl tests\fixtures\mini_msmarco_xi.jsonl `
  --output-dir index\dev

.\.venv\Scripts\python.exe -m src.query `
  --index-dir index\dev `
  --text "How does retrieval augmented generation reduce hallucinations?"
```

## Build multilingual indexes

The active application expects a language-root directory such as `index\semantic_multilingual\hi`, `index\semantic_multilingual\kn`, and `index\semantic_multilingual\te`.

First acquire the official corpus files using the project downloader and build the capped multilingual indexes. The corpus-derived files and generated indexes are intentionally excluded from Git because they are large, reproducible artifacts.

```powershell
# Configure HF_TOKEN in your local .env first when required.
powershell -ExecutionPolicy Bypass -File tools\download_remaining_languages.ps1

.\.venv\Scripts\python.exe -m src.ingest_multilingual `
  --languages hi kn te `
  --split validation `
  --limit 1000 `
  --output-root index\semantic_multilingual
```

For controlled model-comparison experiments, use:

```powershell
.\.venv\Scripts\python.exe tools\build_model_comparison_index.py `
  --model intfloat/multilingual-e5-small `
  --output-root index\e5_small_multilingual `
  --eval-root artifacts\evaluation `
  --strategy sentence
```

## Run the local application

```powershell
.\.venv\Scripts\python.exe -m src.serve `
  --index-dir index\semantic_multilingual `
  --host 127.0.0.1 `
  --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The interface supports typed queries, language switching, evidence display, optional voice capture, and optional grounded answer generation.

## Testing and evaluation

Run the regression suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Run the supplied official retrieval benchmark after the active Hindi index is available:

```powershell
.\.venv\Scripts\python.exe -m app.benchmark 50
```

The benchmark performs its own warm-up and exits with a non-zero status when the P95 total exceeds the configured 50 ms budget. It measures embedding plus local retrieval/ranking. It does not measure browser audio capture, network speech-to-text, or answer generation.

Run the live multilingual text-API diagnostic:

```powershell
.\.venv\Scripts\python.exe tools\benchmark_api_text.py `
  --base-url http://127.0.0.1:8000 `
  --eval-root artifacts\evaluation `
  --queries-per-language 30 `
  --output artifacts\evaluation\live_text_api_benchmark.md
```

### Published local evidence

| Evidence | Result |
|---|---|
| Final official E5 check | Total P95: **44.16 ms** for the supplied 50-query benchmark. |
| Repeated official E5 checks | Total P95: **36.11 ms**, **31.55 ms**, and **39.59 ms**. |
| Regression suite | **12 passing tests** in the final local validation. |
| Quality comparison | E5 improved aggregate Recall@5 from `0.4100` to `0.5200`, Recall@10 from `0.5433` to `0.6800`, and MRR from `0.2530` to `0.3247` on the fixed evaluation set. |

See [`OFFICIAL_BENCHMARK_COMPLIANCE.md`](OFFICIAL_BENCHMARK_COMPLIANCE.md) and [`artifacts/evaluation/`](artifacts/evaluation/) for scope and exact captured outputs.

## Deployment notes

Deploy the current Python service as a single backend-plus-web process. Use a Python-capable host, bind to `0.0.0.0:$PORT`, include the active indexes, and configure all credentials as server-side environment variables. HTTPS is required for reliable browser microphone access in production.

Supabase can support Auth, PostgreSQL, file storage, and optional future vector storage. It should not replace the running Python retrieval service in the current submission configuration.

### Vercel frontend demonstration

`vercel.json` publishes the static `web/` directory to Vercel. When the frontend is opened on Vercel without a configured public backend, it intentionally disables query and voice controls and states that the retrieval API is not connected. This is an accurate public interface demonstration, not a deployed RAG service.

After deploying the Python service separately, update `web/app-config.js` with its public HTTPS origin, for example:

```javascript
window.CONTEXTLINE_API_BASE_URL = "https://contextline-api.example.com";
```

The Python service must then allow the Vercel domain through CORS and retain all provider keys only in its server-side environment. Re-run the multilingual and official benchmarks against the public deployment before describing the full RAG application as live.

## Documentation

| Document | Description |
|---|---|
| [Architecture](ARCHITECTURE.md) | Components, interfaces, and data flow. |
| [Evaluation](EVALUATION.md) | Quality, latency, and evidence methodology. |
| [Guardrails](GUARDRAILS.md) | Safety and grounding controls. |
| [Official benchmark compliance](OFFICIAL_BENCHMARK_COMPLIANCE.md) | Benchmark adapter, measured results, and rollback procedure. |
| [Usage](USAGE.md) | Local workflow and command details. |
| [Multilingual status](MULTILINGUAL_STATUS.md) | Supported-language scope and index status. |

## Data and model references

[1]: https://huggingface.co/datasets/ai4bharat/MSMARCO-XI "AI4Bharat MSMARCO-XI dataset card"
[2]: https://huggingface.co/intfloat/multilingual-e5-small "Multilingual E5 Small model card"
[3]: https://ai-labs.olakrutrim.com/models/Vyakyarth-1-Indic-Embedding "Vyakyarth-1-Indic-Embedding model page"
