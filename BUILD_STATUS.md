# Build Status — Local Interface and API-Ready RAG

**Updated:** 19 August 2026  
**Scope:** Runnable local retrieval application with browser interface, secure provider adapters, and grounded-generation safeguards.

## Completed

A dependency-free local text-retrieval baseline is now present in this project.
It uses the official competition dataset identifier, `ai4bharat/MSMARCO-XI`, in
its hosted-data adapter and documentation. The implementation includes a
normalized data model, provenance-preserving chunking, deterministic hashing
vectors, BM25, Reciprocal Rank Fusion, a structured query response, a
similarity-floor refusal path, index persistence, and a retrieval evaluation
command.

| Component | Location | Status |
|---|---|---|
| Dataset and fixture adapters | `src/data.py` | Implemented |
| Fixed and sentence-aware chunking | `src/chunking.py` | Implemented |
| Dense hashing vectors, BM25, and RRF | `src/retrieval.py` | Implemented |
| Grounded text query and refusal path | `src/pipeline.py`, `src/query.py` | Implemented |
| Index builder | `src/ingest.py` | Implemented |
| Retrieval evaluation | `src/evaluate.py` | Implemented |
| Offline test fixture | `tests/fixtures/mini_msmarco_xi.jsonl` | Implemented |
| Standard-library test suite | `tests/test_baseline.py`, `tests/test_providers.py` | Implemented |
| Sarvam voice adapter | `src/providers.py` | Configured locally and live-validated |
| Structured grounded generation | `src/providers.py`, `src/pipeline.py` | Credential configured; provider request blocked by account quota |
| Local HTTP API and browser interface | `src/serve.py`, `web/` | Implemented and running locally |

## Validation performed

The offline fixture was indexed successfully with the sentence-aware strategy.
A text query returned grounded context and source chunk IDs. A query run with a
similarity floor of `1.0` returned the intended refusal response. The
standard-library test suite completed successfully:

```text
Ran 6 tests in 0.007s
OK
```

The fixture evaluation reported Recall@5 = 1.0000, Recall@10 = 1.0000, and MRR
= 1.0000 over three fixture queries. These values demonstrate that the local
pipeline and metric calculation work; they are **not competition performance
results** and must not be used in a submission. The local browser interface was
also started successfully at `http://127.0.0.1:8000`: a typed BM25 query showed
retrieved evidence and timings, while an enabled but unconfigured generator
returned the intended fail-closed grounded refusal. A local spoken probe was
also transcribed successfully by Sarvam as `en-IN`, then passed through the
retrieval pipeline without answer generation.

## Pending before real-corpus evaluation

The code path for `--dataset ai4bharat/MSMARCO-XI` is ready, but the optional
Hugging Face package download did not complete in this environment because its
large binary dependency stalled. The dependency is isolated in
`requirements-hf.txt` so this does not block offline development.

On a reliable connection, run:

```powershell
pip install -r requirements-hf.txt
python -m src.ingest `
  --dataset ai4bharat/MSMARCO-XI `
  --language hi `
  --split validation `
  --limit 1000 `
  --output-dir index\hi-dev
```

Then inspect `dataset.features`, log a sanitized sample, and generate an
actual held-out evaluation report. The STT and grounded-generation adapters are
already implemented. Sarvam is configured and was validated with a local voice
probe. The OpenAI-compatible credential is configured locally, but the provider returned an insufficient-quota response during validation. Add available provider credits or configure a compatible alternative before describing that generation stage as live.

## References

[1] [HH Goa Task 2 document](https://docs.google.com/document/d/1gzPyuYMaJGnv7mjPZ7Z_e20VxP0j5PMOPi8WmBi8rFk/edit?tab=t.0)

[2] [AI4Bharat MSMARCO-XI dataset card](https://huggingface.co/datasets/ai4bharat/MSMARCO-XI)
