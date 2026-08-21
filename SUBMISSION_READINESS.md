# Contextline — HH Goa Voice RAG Submission Readiness

**Updated:** 20 August 2026  
**Scope:** Local application, reproducible evaluation evidence, demonstration guidance, and submission hand-off.

## Purpose and evidence standard

This package records what has been **verified locally** and separates it from items that still require a team member, such as recording a real microphone demo, hosting the app, creating a repository, or publishing content. It must be used together with the competition brief, which remains the controlling source for final eligibility, file naming, deadlines, and submission links.[1]

> Do not describe the retrieval-only benchmarks in this document as full voice-to-answer performance. They deliberately exclude browser audio capture, network speech-to-text, and answer generation.

## Verified local application state

The browser application is running locally at `http://127.0.0.1:8000`. The health route reports that Hindi, Kannada, and Telugu indexes are available, with Sarvam transcription and the grounded-generation provider configured. The code uses evidence retrieval before generation, returns source chunks, and includes an early unsafe-input refusal path.

| Component | Verified state | Primary evidence |
|---|---|---|
| Local browser/API service | Listening on `127.0.0.1:8000`; `GET /api/health` returns `status: ok` | Live local health check |
| Language indexes | Hindi: 11,240 chunks; Kannada: 10,177; Telugu: 10,237 | `/api/health` and `index/semantic_multilingual/` |
| Input guardrail | Unsafe requests receive an early refusal rather than entering retrieval or generation | `src/guardrails.py`, `src/pipeline.py`, and unit tests |
| Grounding guardrail | Generation is constrained to cited retrieved chunks; provider errors fail closed | `src/providers.py` and `src/pipeline.py` |
| Unit-test suite | The last recorded suite result was 12 passing tests | `tests/` and validation command below |
| Chunking comparison | Five provenance-preserving strategies were compared over saved official validation records | `artifacts/evaluation/chunking_strategy_comparison.md` |

## Reproducible local validation

Run these commands from the project root in PowerShell. They do not publish content or send credentials outside the configured providers.

```powershell
Set-Location 'C:\Users\yashw\Desktop\goa hacker house'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 15 | ConvertTo-Json -Depth 5
.\.venv\Scripts\python.exe tools\benchmark_api_text.py `
  --base-url http://127.0.0.1:8000 `
  --eval-root artifacts\evaluation `
  --queries-per-language 30 `
  --output artifacts\evaluation\live_text_api_benchmark.md
```

The latest live API benchmark used 30 official validation queries per language with `generate=false`. It measures the local text request path only.

| Language | Client-wall P50 / P70 / P100 (ms) | Server API P50 / P70 / P100 (ms) | Retrieval P50 / P70 / P100 (ms) |
|---|---:|---:|---:|
| Hindi | 61.672 / 64.717 / 122.269 | 59.891 / 62.771 / 73.282 | 59.787 / 62.663 / 73.183 |
| Kannada | 94.839 / 106.295 / 138.293 | 92.915 / 104.200 / 136.253 | 92.805 / 104.091 / 136.120 |
| Telugu | 103.617 / 112.015 / 150.099 | 101.423 / 110.278 / 148.033 | 101.303 / 110.163 / 147.894 |

The lower latency figures above are encouraging diagnostic results for the local retrieval path. They are **not** proof that an end-to-end voice request, including microphone capture, remote STT, and grounded answer generation, meets any end-to-end latency target.

## Submission evidence map

| Submission claim | File or reproducible source | Claim boundary |
|---|---|---|
| Uses the official corpus | `artifacts/evaluation/*_official_validation_1000.jsonl`, `src/data.py` | The currently indexed development scope is a frozen 1,000-row validation slice per language; state this explicitly. |
| Multilingual retrieval | `index/semantic_multilingual/`, `artifacts/evaluation/semantic_multilingual_benchmark_optimized.md` | Covers Hindi, Kannada, and Telugu local indexes. |
| Strategy comparison | `artifacts/evaluation/chunking_strategy_comparison.md` | Compares `fixed`, `fixed_overlap`, `sentence`, `semantic`, and `passage` using deterministic hybrid retrieval. |
| Live local API latency | `artifacts/evaluation/live_text_api_benchmark.md` | Retrieval-only text API; no STT, browser capture, or LLM generation. |
| Safe refusal behavior | `src/guardrails.py`, `src/pipeline.py`, `tests/test_baseline.py` | Demonstrate with a harmlessly described unsafe-request test; do not include harmful instructions in the video. |
| Grounded answers | `src/providers.py`, browser evidence, and returned `retrieved_context` | Demonstrate only while the configured provider is functioning, and show citations alongside the answer. |

## Required demonstration recording guide

Record one clear, continuous demonstration rather than splicing isolated screenshots. Begin by showing the local page and the selected language. State that the project uses an indexed Hindi, Kannada, and Telugu slice of `ai4bharat/MSMARCO-XI`, then show the language selector and the source-count interface.

| Segment | What to demonstrate | Recording notes |
|---|---|---|
| Opening | Application title, local URL, and language selector | Do not expose `.env` files, API keys, private folders, or terminal secrets. |
| Hindi text query | Enter a corpus-relevant Hindi question with **Generate answer** enabled | Show the grounded answer, retrieved chunks, citations, and timing cards. |
| Voice flow | Allow microphone access, record a short Hindi question, and wait for the response | Capture the transcript, answer or refusal, sources, and displayed STT/generation/browser timing. This is the only valid evidence for a voice-flow claim. |
| Multilingual coverage | Switch to Kannada and Telugu; run one short text query in each | Show language badges and evidence chunks rather than assuming one index proves all languages. |
| Safety/grounding | Use a short request that the product should refuse, or a clearly unsupported corpus question | Show the refusal state and explain that the system avoids unsupported output. |
| Benchmark evidence | Briefly open `live_text_api_benchmark.md` and `chunking_strategy_comparison.md` | State that these are local retrieval diagnostics, not end-to-end voice numbers. |

## Team-owned completion checklist

The following actions cannot be truthfully completed without team participation, their accounts, or an explicit decision to publish. Complete each item before final submission and preserve its resulting link or file in the hand-off directory.

| Action | Owner | Completion evidence |
|---|---|---|
| Record a real Hindi voice-to-answer run | Team member with microphone | Raw screen recording plus a screenshot showing transcript, source chunks, and timing cards |
| Repeat one language-switch check for Kannada and Telugu | Team member | Continuous recording or separate dated screenshots for each language |
| Validate provider quota immediately before filming | Team member controlling the provider account | Successful generated grounded answer with citations, or an explicit decision to demonstrate fail-closed mode |
| Publish a stable hosted instance | Team member controlling hosting | Public URL, deployment settings, and a smoke-test capture |
| Create or update the source repository | Team member controlling the repository | Repository URL, commit hash, README, and sanitized `.env.example` only |
| Produce required presentation/process/demo videos | Team members | Final video files and publicly accessible links if required by the brief |
| Complete mandated social promotion | Each required team member | Post URLs and screenshots showing the account, date, and content |
| Check the final form against the competition brief | Submission owner | Completed submission form, uploaded artifacts, and confirmation receipt |

## Final pre-submit decision

Do not submit with an unsupported performance statement. The proposed final narrative is that **Contextline is a working local multilingual, voice-capable RAG prototype with grounded citations, safety refusal behavior, reproducible chunking experiments, and measured local retrieval-path latency**. Only add an end-to-end voice-latency claim after recording and measuring an actual voice request under the same conditions used for the claim.

## References

[1]: https://docs.google.com/document/d/1gzPyuYMaJGnv7mjPZ7Z_e20VxP0j5PMOPi8WmBi8rFk/edit "HH Goa 2026 Task 2 competition brief"
[2]: https://huggingface.co/datasets/ai4bharat/MSMARCO-XI "AI4Bharat MSMARCO-XI dataset card"
