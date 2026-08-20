# Voice-Enabled RAG — HH Goa 2026, Task 2

## What this is

A voice-enabled Retrieval-Augmented Generation system. A user speaks a
question → the pipeline transcribes it → retrieves relevant context from
`ai4bharat/MSMARCO-XI` → generates a grounded answer, end to end.

Pipeline shape (from the task brief):
`Voice input → Speech-to-text → Chunking/Retrieval (vector DB) → Answer generation`

This document is the **source of truth for what we're building and why**.
`ARCHITECTURE.md` covers how the pieces fit together technically.
`USAGE.md` covers how to run it. `EVALUATION.md` covers how we prove any
of it actually works.

---

## Verified dataset integration: `ai4bharat/MSMARCO-XI`

The official HH Goa Task 2 document links directly to
[`ai4bharat/MSMARCO-XI`](https://huggingface.co/datasets/ai4bharat/MSMARCO-XI),
not `MSMARCO-IIX`. Its dataset card describes translated MS MARCO records for
14 Indic-language configurations: Assamese, Bengali, Gujarati, Hindi, Kannada,
Malayalam, Marathi, Nepali, Odia, Punjabi, Sanskrit, Tamil, Telugu, and Urdu.

Each row contains a translated `query`, `Answer`, `query_id`, `query_type`,
and a `passages` object. The object holds parallel `Translated_passages` and
`is_selected` lists, alongside the original English passages. The ingestion
adapter flattens `Translated_passages` into searchable records and preserves
`is_selected` as the retrieval relevance signal. This supports a direct,
corpus-native evaluation instead of a synthetic query set.

The dataset card lists train and validation files per language. Start with one
language and a capped validation subset—for example:

```python
dataset = load_dataset("ai4bharat/MSMARCO-XI", "hi", split="validation")
```

The public dataset viewer was unavailable during project setup, so the
implementation must still log `dataset.features`, row counts, and a sanitized
sample after the first successful download. This is a runtime validation step,
not a reason to substitute a different dataset.

**Implementation implication:** rows are query-grouped passage sets rather
than independently authored long documents. Fixed and sentence-aware chunking
are valid baselines; defer late chunking and proposition decomposition until a
length-distribution check demonstrates that they add meaningful value.

---

## Goals, in priority order

1. **Retrieval that's actually good** — not "a vector DB exists," but
   retrieval strategies that are benchmarked against each other and
   against ground truth, with a defensible reason for what shipped.
2. **Fast where it can be, honest where it can't** — the brief's <50ms
   target applies to the full pipeline (chunking + vector DB retrieval +
   everything through to output). Retrieval itself can realistically hit
   sub-50ms with an in-process ANN index. STT and LLM generation cannot —
   cloud API round-trips for either typically run hundreds of ms.
   Rather than hide that, the system **instruments every stage
   separately** and reports true P50/P70/P100 for both the full pipeline
   and the retrieval-only sub-path, so the numbers tell the real story
   instead of one blended average.
3. **Actually advanced, not just more parts** — two ideas carry the
   "advanced" claim, not five buzzwords:
   - **Late chunking** — embed the full document first, split into
     chunks *after*, so each chunk vector is contextualized by the whole
     document rather than isolated. Fixes a real, known failure mode of
     every naive chunking approach (a chunk like "it caused a 40% rise"
     has no idea what "it" refers to once split in isolation).
   - **Adaptive fast/deep retrieval paths, gated by confidence** — the
     system decides *how hard* to search per query, rather than doing a
     fixed amount of work every time. Cheap hybrid retrieval by default;
     escalate to reranking (+ optional query expansion) only when the
     cheap path isn't confident. This is the actual resolution to
     "make it faster AND more advanced" — those two asks pull in
     opposite directions unless the system branches.
4. **Grounded, not confidently wrong** — the system must be able to say
   "I don't have enough information" instead of generating a plausible
   but unsupported answer. This is graded explicitly (guardrails
   section of the brief) and it's also just correct system design.

## Non-goals

- We are not trying to beat published MSMARCO leaderboard numbers.
  This is a demonstration of RAG engineering judgment on a fixed
  timeline, not a research contribution.
- We are not implementing every technique listed in `ARCHITECTURE.md`
  as a hard requirement. Several are marked **stretch / toggle** —
  implemented, documented, and demonstrably working, but not
  necessarily in the default hot path. Being explicit about what's
  default vs. optional is itself part of showing engineering judgment.

## Deliverables (from the task brief)

- Submission form: `https://forms.gle/MNvCjcv23Hn2Eeu58`
- GitHub repo link
- Live working link
- 2 videos:
  - **Video 1 — Team/process** (90 sec): shows the team working on this,
    not the product itself
  - **Video 2 — Demo**: the actual project working end to end
- No resubmissions — submit only when the build is final

Tag: `#RAGInGoa`

## Document map

| File | Purpose |
|---|---|
| `PROJECT.md` | This file — what and why |
| `ARCHITECTURE.md` | How the system is built, layer by layer, with the fast/deep path design |
| `USAGE.md` | How to set up, run, and query the system |
| `EVALUATION.md` | How we measure retrieval quality and latency, and what "vast chunking comparison" actually means as a deliverable |
| `GUARDRAILS.md` | Guardrail design in detail — the checks, their thresholds, and why each exists |
