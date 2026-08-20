# Usage

This guide covers the **implemented local retrieval baseline**. It loads the
competition-linked `ai4bharat/MSMARCO-XI` corpus, creates a local hybrid index,
and returns grounded retrieved context for text queries. Voice transcription,
LLM generation, reranking, and HTTP serving are planned next stages and are not
silently simulated here.

## Prerequisites

- Python 3.10 or later.
- Internet access only for a Hugging Face corpus download.
- No API key is required for the baseline fixture, ingestion, or text query.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
# Needed only before loading the hosted competition corpus.
pip install -r requirements-hf.txt
copy .env.example .env
```

## Fast offline smoke test

The repository includes a small normalized fixture so the full local retrieval
path can be validated before downloading the competition corpus.

```powershell
python -m src.ingest `
  --source-jsonl tests\fixtures\mini_msmarco_xi.jsonl `
  --output-dir index\dev

python -m src.query `
  --index-dir index\dev `
  --text "How does retrieval augmented generation reduce hallucinations?"
```

The query command returns structured JSON with the retrieved chunk identifiers,
retrieval scores, context, a confidence value, refusal status, and per-stage
latency values. The baseline deliberately does **not** generate an LLM answer:
it returns only context that can be traced to the index.

## Build an index from the competition corpus

Use the exact dataset named in the official task document:
`ai4bharat/MSMARCO-XI`. Choose a single language configuration and begin with a
small validation slice.

```powershell
python -m src.ingest `
  --dataset ai4bharat/MSMARCO-XI `
  --language hi `
  --split validation `
  --limit 1000 `
  --chunking-strategy sentence `
  --output-dir index\hi-dev
```

The supported language configurations include `as`, `bn`, `gu`, `hi`, `kn`,
`ml`, `mr`, `ne`, `or`, `pa`, `sa`, `ta`, `te`, and `ur`.[1]

### Implemented chunking strategies

| Strategy | Command value | Status |
|---|---|---|
| Fixed-size baseline | `fixed` or `fixed_overlap` | Implemented |
| Sentence-aware baseline | `sentence` or `semantic_baseline` | Implemented |
| Late chunking | — | Deferred until corpus length analysis |
| Proposition decomposition | — | Deferred until a measured quality case exists |

## Query an index

```powershell
python -m src.query `
  --index-dir index\hi-dev `
  --text "your question" `
  --top-k 5
```

To demonstrate a refusal path while testing, set a deliberately high threshold:

```powershell
python -m src.query `
  --index-dir index\dev `
  --text "an unrelated question" `
  --minimum-similarity 1.0
```

## Evaluate retrieval quality and retrieval latency

The evaluation command groups normalized records by `query_id`, treats
`selected=true` records as relevance labels, and reports Recall@5, Recall@10,
MRR, and retrieval-only P50/P70/P100 latency.

```powershell
python -m src.evaluate `
  --index-dir index\dev `
  --eval-jsonl tests\fixtures\mini_msmarco_xi.jsonl `
  --output eval\results\dev-baseline.md
```

Do not present fixture results as competition results. For final reporting, use
a frozen real-corpus evaluation split and record language, corpus size, chunking
settings, environment, and model version.

## Run the local browser interface

The server keeps the browser interface and API keys on the local machine. Copy the template, enter real provider keys only in your git-ignored `.env` file, then start the service:

```powershell
copy .env.example .env
# Add SARVAM_API_KEY and OPENAI_API_KEY to .env.
python -m src.serve --index-dir index\dev --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Typed retrieval needs no API key. The **Record voice** control uploads a short browser recording to Sarvam’s REST transcription endpoint when `SARVAM_API_KEY` is present. The **Generate answer** toggle sends retrieved context only—not the full index—to the configured OpenAI-compatible generation endpoint.

If generation returns malformed JSON, missing citations, or a citation that is not among the retrieved chunk IDs, the server fails closed and returns no generated answer. This is intentional grounding behavior.

## Current limits and next stages

| Capability | Current state | Next implementation step |
|---|---|---|
| Voice input | Sarvam REST adapter and browser recorder implemented | Add a real provider key, then validate short audio across the selected language. |
| Answer generation | OpenAI-compatible structured-output adapter implemented | Add a real provider key and run grounded-answer red-team tests. |
| Dense vectors | Deterministic hashing-vector baseline | Replace with a multilingual embedding model and FAISS/HNSW after evaluation. |
| Fast/deep routing | Not implemented | Calibrate a confidence gate and add cross-encoder reranking. |
| HTTP API/UI | Local browser interface and JSON API implemented | Deploy only after real-corpus and provider validation. |

## References

[1] [AI4Bharat MSMARCO-XI dataset card](https://huggingface.co/datasets/ai4bharat/MSMARCO-XI)
