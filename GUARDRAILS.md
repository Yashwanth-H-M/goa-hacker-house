# Guardrails

The brief (§6) asks for four things explicitly: handling for off-topic
queries, unsafe/inappropriate inputs, hallucination checks, and answers
not grounded in retrieved context. "Show that your system knows when
*not* to answer, not just how to answer" is the actual grading bar — a
system that never refuses hasn't demonstrated this, no matter how good
its answers are otherwise.

## 1. Off-topic queries

**Where:** immediately after STT, before retrieval (Layer 2 in
`ARCHITECTURE.md`) — cheapest place to reject, before spending a
retrieval or generation call on a query the system has no business
answering.

**How:** embed the query, compare against a corpus-level similarity
signal (centroid similarity, or max similarity against a sample of
corpus chunk embeddings). Below a tuned threshold → short-circuit
immediately with a plain "this is outside what I can answer from this
dataset" response.

**Why here and not later:** an off-topic query that reaches generation
has already cost a retrieval call for nothing, and risks the LLM
generating a plausible-sounding answer from general knowledge instead of
the corpus — exactly the failure mode this whole system exists to avoid.

## 2. Unsafe / inappropriate input

**Where:** same stage as off-topic checking, on the same transcribed
text.

**How:** lightweight content filter — a small classifier or a
keyword/toxicity check, run before any retrieval work. Flagged input
short-circuits to a refusal, same as off-topic.

**Why separate from off-topic:** the two failure modes are different in
kind (an unsafe query might be perfectly "on topic" for the corpus but
still inappropriate to answer), so they're checked as two independent
conditions at the same stage rather than folded into one score.

## 3. Hallucination check

**Where:** after generation (Layer 7), acting on the structured output
from Layer 6.

**How, mechanically:** generation is *forced* to cite chunk IDs for
every claim (Layer 6's structured output —
`{answer, cited_chunk_ids, confidence}`). The guardrail verifies:

- Every cited chunk ID actually exists in the retrieved set (cheap,
  no extra model call — this alone catches a generation that invents a
  citation).
- **Stronger, optional layer:** an LLM-as-judge pass checking that each
  cited chunk *actually supports* the specific claim attributed to it,
  not just that the ID is real. This costs an extra call and is a
  documented stretch layer, not assumed to run on every query by
  default.

**Why forced citations beat a purely post-hoc checker:** constraining
generation to only make citable claims is a stronger defense than
generating freely and auditing afterward, because the model is
structurally nudged toward grounded output at generation time rather
than being caught after the fact.

## 4. Not grounded in retrieved context / refuse-to-answer

**Where:** this is actually two checks at two different points, and
they're kept distinct rather than merged:

- **Pre-generation** (Layer 5, confidence gate): if the top retrieval
  result is below a similarity floor, generation is skipped entirely —
  the system returns "I don't have enough information to answer that"
  directly, without ever asking the LLM to try.
- **Post-generation** (Layer 7, same as hallucination check): if
  citation coverage is thin (most of the answer's claims have no valid
  citation) even though *some* retrieval happened, that's a distinct
  failure mode from "retrieval found nothing" — the system found
  something, but the answer went beyond what that something actually
  supports.

**Why this matters more than it might look:** most naive RAG
implementations only have the second check, or neither. A system that
always attempts generation regardless of retrieval quality will produce
fluent, confident, wrong answers on exactly the queries where it should
be most cautious. Building the pre-generation refusal path in from the
start (not bolted on after the demo works) is what actually
demonstrates "knows when not to answer" rather than just asserting it
in a slide.

## Thresholds

Specific numeric thresholds (similarity floors, confidence cutoffs) are
**not hardcoded as final here** — they need to be tuned against real
retrieved-score distributions from the actual corpus, which in turn
depends on the dataset-schema question flagged in `PROJECT.md`. Treat
every threshold in the implementation as a starting point validated
against `EVALUATION.md`'s eval set, not a number picked once and left
alone.
