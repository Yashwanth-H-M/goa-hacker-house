# Architecture

This is the technical design, layer by layer. Each layer names the
standard approach, its known weakness, and what we do instead — and is
marked **default** (ships in the hot path) or **stretch** (implemented
and documented, toggle-only).

See `PROJECT.md` for the verified `ai4bharat/MSMARCO-XI` integration.
The first successful corpus load must still record real field types and passage
length distributions; decisions that depend on those observed properties are
flagged inline.

---

## Full pipeline

```
voice_in
  → STT (Sarvam)                              [retry, timeout]        DEFAULT
  → input_guardrail (unsafe / off-topic)       [short-circuit on fail] DEFAULT
  → query_embed  ⟍
                  ⟩ parallel                                           DEFAULT
  → BM25_tokenize ⟋
  → hybrid_retrieve (RRF fuse, top-30)         [retry]                 DEFAULT
  → confidence_check
       ├─ high confidence → top-5 straight to generation                DEFAULT (fast path)
       └─ low confidence  → cross-encoder rerank (top-30→top-5)         STRETCH (deep path)
                             [+ optional HyDE query rewrite, off by default]
  → generate (structured JSON output, forced citations)                 DEFAULT
  → grounding_guardrail (citation coverage check)  [flag/refuse]        DEFAULT
  → structured_answer_out
```

Every arrow is a discrete, typed function call with its own error
handling — not a single prompt-in/text-out call. This structure is what
satisfies the brief's "harness" requirement (§5) directly, and it's also
what makes the fast/deep branch possible to build cleanly rather than as
a bolted-on special case.

---

## Layer 1 — STT

**Choice: Sarvam**, not ElevenLabs.

Reasoning: this is an India-context hackathon (#RAGInGoa), the dataset is
an Indic-language resource by name, and Sarvam is built specifically for
Indian languages and accents. ElevenLabs' STT is a fine general-purpose
choice but has no particular edge for this context, and its strength
(very high-quality TTS) isn't something the brief asks for — the pipeline
only needs STT, not a spoken response back. If the confirmed dataset
turns out to be primarily English-language MSMARCO content translated
1:1 with no code-mixing, this choice is worth revisiting, but the
Indic-first assumption is the safer default given the event context.

## Layer 2 — Input guardrail

Runs immediately on the STT output, before any retrieval work happens —
cheapest possible place to reject bad input.

- **Off-topic check** — cheap similarity-to-corpus threshold (embed the
  query, compare to corpus centroid or a sample of corpus embeddings).
  Below threshold → short-circuit with a clear "outside this system's
  scope" response, skip retrieval and generation entirely.
- **Unsafe/inappropriate input check** — lightweight classifier or
  keyword/toxicity filter on the transcribed text.

## Layer 3 — Chunking

**This is the layer most affected by the observed MSMARCO-XI passage-length
distribution.** The dataset structure is documented as query-grouped translated
passages with `is_selected` labels. Techniques below remain hypotheses until
measured against a frozen language-specific evaluation split — see
`EVALUATION.md`.

1. **Late chunking** (Jina AI, 2024) — embed the *entire* document
   through a long-context embedding model (e.g. jina-embeddings-v3)
   first, producing per-token embeddings across the full document, and
   only pool into chunk-level vectors *after*. Each chunk's final vector
   is contextualized by the whole document, which directly fixes the
   classic problem where a chunk like "it caused a 40% rise" loses the
   referent of "it" the moment it's split and embedded in isolation.
   This is a genuine, citable technique most naive implementations won't
   use — it's the strongest candidate for the "vast, not naive" ask.
   **Depends on:** the embedding model's context window comfortably
   covering full source documents. If confirmed passages in the dataset
   are already short (typical MSMARCO passages are ~1-3 sentences), late
   chunking's advantage shrinks — there's less cross-chunk context to
   preserve if the source "documents" are already atomic. **Verify
   passage/document length distribution before committing engineering
   time here.**

2. **Proposition-based chunking** — decompose text into atomic,
   self-contained factual statements (via one LLM pass at index time)
   rather than arbitrary token spans. It may help factual QA retrieval,
   but MSMARCO-XI already provides query-grouped passages and answers.
   Implement it only after the baseline quality comparison demonstrates
   a measurable gain that justifies its indexing cost.

3. **Semantic chunking** — split on embedding-similarity breakpoints
   (e.g. LangChain's `SemanticChunker`, or a manual cosine-distance
   threshold over sentence embeddings) rather than a fixed token count.
   Compare it against the fixed and sentence-aware baselines using the
   dataset's `is_selected` labels; do not assume it will improve already
   short passages.

4. **Metadata-aware / structure-preserving chunking** — never chunk
   across an MSMARCO-XI passage boundary. Preserve `query_id`, language,
   source passage index, and `is_selected` through every transformation
   so evaluation can map a returned chunk back to its source passage.

5. **Fixed-size ± overlap** — included **only** as the explicit
   naive baseline the brief says not to submit alone. Every other
   strategy is benchmarked against this as the floor.

## Layer 4 — Retrieval

**Hybrid: dense + sparse, fused with Reciprocal Rank Fusion (RRF).**

- **Dense**: embedding model + FAISS with an HNSW index, in-process (no
  network round-trip to a hosted vector DB — this is the single biggest
  available latency win for this leg specifically).
- **Sparse**: BM25 (`rank_bm25` or a proper inverted index) over the same
  chunks. Catches exact-match / rare-term / entity queries that dense
  embeddings structurally blur over — a well-documented dense-retrieval
  weakness, not a hypothetical one.
- **Fusion**: RRF rather than a learned or hand-tuned weight between the
  two — parameter-free, robust, defensible without a tuning pass we
  don't have eval budget for.

Dense embedding and BM25 tokenization run **in parallel** (they're
independent of each other), not sequentially — a real, if modest,
latency saving in the harness's async orchestration.

**DEFAULT** output: top-30 candidates from RRF fusion.

## Layer 5 — Confidence gate (fast path vs. deep path)

This is the layer that resolves "make it faster AND more advanced"
architecturally instead of picking one:

- Compute a confidence signal from the fused retrieval result — e.g.
  the RRF score gap between rank-1 and rank-5, or the raw top-1
  similarity score.
- **High confidence → fast path (DEFAULT):** take top-5 directly to
  generation. No reranker, no query rewrite. This is the
  latency-optimized default path for the common case.
- **Low confidence → deep path (STRETCH):**
  - **Cross-encoder reranking** — re-score the top-30 with a
    cross-encoder (e.g. `bge-reranker-base`) that sees query and passage
    *together*, catching relevance signals bi-encoders can't by
    construction. This is the single highest-leverage retrieval-quality
    upgrade available and it's cheap here specifically because it only
    touches 30 candidates, not the full corpus.
  - **Optional HyDE query rewrite** (off by default, toggle-able) —
    before retrieving, a small/fast LLM generates a hypothetical answer
    to the query, and *that* gets embedded and searched instead of the
    raw query. Often retrieves better because a hypothetical answer is
    lexically/semantically closer to the real target passage than the
    question is. Real added latency cost (one extra LLM call) — this is
    exactly the kind of thing worth having implemented and demoable, not
    silently defaulted on.

This means the system does a fixed cheap amount of work for easy
queries and only pays the expensive-but-better cost when the cheap path
signals it isn't confident — adaptive retrieval effort, not a fixed
budget spent identically on every query regardless of difficulty.

## Layer 6 — Generation

- **Structured output** — the LLM returns
  `{answer, cited_chunk_ids, confidence}` as JSON via function-calling /
  tool-call schema, not free text parsed with regex after the fact.
- **Citation-forced generation** — every claim in the answer must
  reference a chunk ID. This constrains generation directly rather than
  auditing it after the fact, which is a stronger hallucination defense
  than a purely post-hoc checker.

## Layer 7 — Grounding guardrail

- Verify every cited chunk ID in the structured output actually exists
  in the retrieved set (mechanical check, no extra LLM call needed).
- Optional stronger layer: LLM-as-judge pass checking that cited chunks
  actually support the specific claim attributed to them, not just that
  the ID is real.
- **Refuse-to-answer path** — if the top retrieval result is below a
  similarity floor at Layer 4/5, skip generation and return "I don't
  have enough information to answer that" directly. This path is
  explicitly called out in the brief ("show your system knows when *not*
  to answer") and is built in from the start, not added at the end.

---

## Latency instrumentation

Every stage in the pipeline diagram above is timed independently. The
brief's <50ms target (§3) applies to the *entire* process — chunking
(at query time, this means retrieval indexing lookups, not re-chunking
the corpus) + vector DB retrieval + everything through to final output.

STT and LLM generation are cloud API calls that typically run hundreds
of ms to low seconds each — that's a property of using hosted APIs, not
something the harness can architect away. Rather than obscure this, the
system reports:

- **Full pipeline P50/P70/P100**, across a real query set (per the
  brief's §4 — not a single best-case run)
- **Retrieval-only P50/P70/P100**, isolated from STT/generation, since
  this sub-path is realistically where sub-50ms is achievable with an
  in-process FAISS HNSW index

Both numbers are reported side by side. This is more honest and more
informative than a single blended average, and it directly demonstrates
understanding of *where* the latency budget goes rather than just
producing one number.

## Semantic response cache (STRETCH)

Cache query embeddings for recently answered queries. On a new query,
if cosine similarity to a cached query exceeds a high threshold (e.g.
0.97), skip retrieval + generation and serve the cached answer with a
note that it's a cached response. This is a real production RAG
pattern (the same idea underlies tools like GPTCache) — implemented and
documented, but not something the demo/eval query set is expected to
exercise heavily, since it depends on query repetition.

## Stack summary

| Component | Choice | Why |
|---|---|---|
| STT | Sarvam | Indic-language/accent fit for the event context |
| Embedding model | Long-context model supporting late chunking (e.g. jina-embeddings-v3) | Needed for Layer 3's core technique |
| Vector index | FAISS (HNSW) | In-process, no network hop, fastest available option for the retrieval leg |
| Sparse index | BM25 (`rank_bm25`) | Catches exact-match failures of dense-only retrieval |
| Fusion | Reciprocal Rank Fusion | Parameter-free, robust, no tuning pass required |
| Reranker (deep path) | Cross-encoder (e.g. `bge-reranker-base`) | Query+passage joint scoring, only run on top-30 |
| Generation | Structured/tool-call output, forced citations | Makes grounding checks mechanical |
| Orchestration | Async harness, per-stage retry/timeout | Satisfies §5, enables parallel stages and the confidence branch |
