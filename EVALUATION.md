# Evaluation

This is what makes "vast chunking comparison" (brief §2) and honest
"P50/P70/P100" latency numbers (brief §4) an actual deliverable rather
than a claim. The official `ai4bharat/MSMARCO-XI` schema documents
query-grouped translated passages and `is_selected` relevance labels; this
document defines how to turn those labels into a reproducible measurement.

---

## Retrieval quality: chunking strategy comparison

### The key move: use the dataset's documented `is_selected` labels

MSMARCO-XI rows contain a translated query and parallel passage arrays.
The matching `is_selected` entry marks whether a passage is relevant to the
query. Flatten each translated passage while retaining `query_id`, the source
passage index, and `is_selected`; a retrieved chunk counts as relevant when
its parent passage is selected.

Use a frozen real-corpus development and test split rather than generating
synthetic questions. Synthetic evaluation may be useful for additional stress
testing later, but it must be reported separately because it does not measure
the competition corpus's native relevance labels.

### What gets compared

Each candidate chunking strategy from `ARCHITECTURE.md` Layer 3:

1. Fixed-size (baseline — the naive approach the brief says not to ship alone)
2. Fixed-size + overlap
3. Semantic (embedding-similarity breakpoints)
4. Metadata-aware / structure-preserving
5. Late chunking
6. Proposition-based (**only if a development-set comparison justifies its
   indexing cost and latency**)

### Metrics

- **Recall@k** (k = 5, 10) — of the queries in the eval set, what
  fraction have the true relevant passage somewhere in the top-k
  retrieved chunks?
- **MRR (Mean Reciprocal Rank)** — rewards ranking the correct passage
  *higher*, not just getting it in the top-k somewhere.
- Report both **per chunking strategy alone** (i.e. dense-only retrieval
  over each chunking method, isolating the chunking variable) and
  **for the final shipped hybrid+RRF pipeline** using whichever chunking
  strategy wins the first comparison. This separates "which chunking
  strategy is best" from "does the full retrieval stack work" — two
  different questions that get conflated if only the final number is
  reported.

### What the deliverable actually looks like

A results table:

| Chunking strategy | Recall@5 | Recall@10 | MRR |
|---|---|---|---|
| Fixed-size (baseline) | — | — | — |
| Fixed-size + overlap | — | — | — |
| Semantic | — | — | — |
| Metadata-aware | — | — | — |
| Late chunking | — | — | — |
| Proposition-based *(if applicable)* | — | — | — |

...plus a short written justification for whichever strategy actually
ships in the default pipeline, referencing this table. **This table is
the deliverable for brief §2** — it's what makes the chunking approach
demonstrably "vast" rather than descriptively vast in five bullet
points with no evidence behind them.

---

## Latency

### Method

Run the full pipeline over a real query set — not five convenient
examples, a set large enough that P70 and P100 are meaningful rather
than noise (the eval query set built for retrieval quality above can
double as this set).

For every query, record wall-clock time at each stage boundary:

```
t0: voice_in received
t1: STT complete
t2: input guardrail complete
t3: hybrid retrieval complete
t4: confidence gate decision made
t5: (if deep path) reranking complete
t6: generation complete
t7: grounding guardrail complete → final answer out
```

From these, compute **per-stage duration**, not just cumulative time —
this is what lets the latency report say *where* time goes instead of
producing one opaque total.

### What gets reported

Two separate P50/P70/P100 tables, not one blended number:

1. **Full pipeline** (t0 → t7) — this is the honest answer to "does the
   whole thing meet the <50ms target," and the honest answer is
   expected to be *no*, because STT and LLM generation are cloud API
   round-trips that structurally cannot complete in 50ms regardless of
   how the rest of the pipeline is engineered.
2. **Retrieval-only** (t2 → t3, i.e. chunking/indexing lookup + vector
   DB retrieval specifically) — this is the sub-path where sub-50ms is
   realistically achievable with an in-process FAISS HNSW index, and
   reporting it separately demonstrates the target was understood and
   pursued where it's actually achievable, rather than the whole
   pipeline being hand-waved as "fast enough."

### Why P50/P70/P100 across a real set, not a best-case run

The brief is explicit about this (§4: "not a single best-case run").
Percentile latency across many queries surfaces the tail — a system
that's fast on P50 but has a long P100 tail (e.g. from occasional STT
API slowness, or queries that trigger the deep retrieval path) tells a
more complete story than an average, and directly informs whether the
fast/deep confidence-gate design (Layer 5) is actually paying off or
just adding complexity.

---

## Fast path vs. deep path: what to actually measure

Because Layer 5 branches based on confidence, latency and quality
numbers should also be reported **split by path taken**:

- What fraction of eval queries triggered the deep path?
- What's the latency delta between fast-path and deep-path queries?
- Did the deep path's queries show a measurable *quality* improvement
  (recall/MRR) over what the fast path would have produced on the same
  queries — i.e., is the confidence gate actually routing the right
  queries to the expensive path, or is it noisy?

This last point is the real test of whether the adaptive-routing idea
in `ARCHITECTURE.md` Layer 5 is doing genuine work or just adding a
branch that doesn't earn its complexity.
