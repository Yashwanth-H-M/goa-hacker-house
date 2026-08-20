"""Text-query pipeline with retrieval grounding, evidence checks, and timings."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from src.guardrails import UNSAFE_INPUT_REFUSAL, check_input_safety
from src.providers import OpenAICompatibleGenerator, ProviderConfigurationError, ProviderRequestError
from src.retrieval import HybridIndex, SearchResult, tokenize


# Function words often dominate short questions but do not demonstrate that a
# passage can support the question.  Keep this compact and language-aware; any
# remaining token is treated as a possible evidence-bearing term.
_NON_EVIDENCE_TOKENS = {
    # English
    "a", "an", "and", "are", "at", "be", "by", "do", "does", "for", "from", "how", "i", "in", "is",
    "it", "of", "on", "or", "the", "to", "was", "what", "when", "where", "which", "who", "why", "with",
    # Hindi
    "का", "की", "के", "को", "क्या", "क्यों", "कैसे", "कहाँ", "कब", "है", "हैं", "था", "थे", "में", "और",
    "या", "पर", "से", "एक", "यह", "वह", "लिए", "हो", "हुआ",
    # Kannada
    "ಏನು", "ಏನು?", "ಏಕೆ", "ಹೇಗೆ", "ಎಲ್ಲಿ", "ಯಾವಾಗ", "ಯಾರು", "ಇದೆ", "ಇದು", "ಅದು", "ಮತ್ತು", "ಅಥವಾ",
    "ನಲ್ಲಿ", "ಗೆ", "ನ", "ಒಂದು", "ಈ", "ಆ", "ರಿಂದ", "ಗಾಗಿ",
    # Telugu
    "ఏమిటి", "ఏంటి", "ఏమి", "ఎందుకు", "ఎలా", "ఎక్కడ", "ఎప్పుడు", "ఎవరు", "ఉంది", "ఇది", "అది", "మరియు",
    "లేదా", "లో", "కు", "ని", "ఒక", "ఈ", "ఆ", "నుండి", "కోసం",
}


@dataclass(frozen=True)
class QueryResponse:
    """Structured response shared by the CLI, browser interface, and future API clients."""

    answer: str
    cited_chunk_ids: list[str]
    confidence: float
    path_taken: str
    refused: bool
    generation_status: str
    guardrail_reason: str | None
    latency_ms: dict[str, float]
    retrieved_context: list[dict[str, object]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "cited_chunk_ids": self.cited_chunk_ids,
            "confidence": round(self.confidence, 4),
            "path_taken": self.path_taken,
            "refused": self.refused,
            "generation_status": self.generation_status,
            "guardrail_reason": self.guardrail_reason,
            "latency_ms": {name: round(value, 3) for name, value in self.latency_ms.items()},
            "retrieved_context": self.retrieved_context,
        }


def _confidence(results: list[SearchResult]) -> float:
    """Return a readable confidence score using semantic retrieval when available."""

    if not results:
        return 0.0
    semantic_score = results[0].semantic_score
    if semantic_score is not None:
        # Indic sentence embeddings use cosine similarity. Map the practical
        # [0.20, 0.95] range into a conservative display score.
        return max(0.0, min(1.0, (semantic_score - 0.20) / 0.75))
    return max(0.0, min(1.0, (results[0].dense_score + 1.0) / 2.0))


def _evidence_terms(text: str) -> set[str]:
    """Return non-function query terms that should be reflected in evidence."""

    return {token for token in tokenize(text) if len(token) > 1 and token not in _NON_EVIDENCE_TOKENS}


def _has_sufficient_evidence(
    query_terms: set[str],
    candidate: SearchResult,
    minimum_coverage: float,
    minimum_semantic_similarity: float,
    minimum_semantic_margin: float,
    best_semantic_score: float | None,
    semantic_margin: float,
) -> bool:
    """Reject a candidate whose passage does not substantively cover the query.

    Reciprocal Rank Fusion always returns dense candidates, even when BM25 has
    no informative match. A candidate must either pass the strict lexical rule
    or be the clearly best Indic semantic candidate above calibrated score and
    margin thresholds.
    """

    if not query_terms:
        return False
    shared_terms = query_terms.intersection(_evidence_terms(candidate.chunk.text))
    required_terms = 1 if len(query_terms) == 1 else 2
    coverage = len(shared_terms) / len(query_terms)
    lexical_evidence = len(shared_terms) >= required_terms and coverage >= minimum_coverage
    semantic_evidence = (
        candidate.semantic_score is not None
        and best_semantic_score is not None
        and abs(candidate.semantic_score - best_semantic_score) < 1e-9
        and candidate.semantic_score >= minimum_semantic_similarity
        and semantic_margin >= minimum_semantic_margin
    )
    return lexical_evidence or semantic_evidence


class TextRAGPipeline:
    """A retrieval-first pipeline with citation-constrained generation.

    Sources are only exposed when their text covers enough content-bearing query
    terms.  This is intentionally conservative because the baseline encoder is
    a deterministic hashing encoder rather than a multilingual semantic model.
    """

    def __init__(
        self,
        index: HybridIndex,
        minimum_similarity: float = -0.05,
        minimum_lexical_coverage: float = 0.75,
        minimum_semantic_similarity: float = 0.45,
        minimum_semantic_margin: float = 0.015,
        generator: OpenAICompatibleGenerator | None = None,
    ) -> None:
        if not 0.0 < minimum_lexical_coverage <= 1.0:
            raise ValueError("minimum_lexical_coverage must be greater than 0 and at most 1.")
        if not -1.0 <= minimum_semantic_similarity <= 1.0:
            raise ValueError("minimum_semantic_similarity must be between -1 and 1.")
        if minimum_semantic_margin < 0.0:
            raise ValueError("minimum_semantic_margin must be non-negative.")
        self.index = index
        self.minimum_similarity = minimum_similarity
        self.minimum_lexical_coverage = minimum_lexical_coverage
        self.minimum_semantic_similarity = minimum_semantic_similarity
        self.minimum_semantic_margin = minimum_semantic_margin
        self.generator = generator

    def query(self, text: str, top_k: int = 5, generate: bool = False) -> QueryResponse:
        overall_start = perf_counter()
        if not text or not text.strip():
            raise ValueError("Query text cannot be empty.")

        input_guardrail_start = perf_counter()
        normalized_query = " ".join(text.split())
        safety_decision = check_input_safety(normalized_query)
        query_terms = _evidence_terms(normalized_query)
        input_guardrail_ms = (perf_counter() - input_guardrail_start) * 1000
        if safety_decision.blocked:
            total_ms = (perf_counter() - overall_start) * 1000
            return QueryResponse(
                answer=UNSAFE_INPUT_REFUSAL,
                cited_chunk_ids=[],
                confidence=0.0,
                path_taken="input_guardrail_refusal",
                refused=True,
                generation_status="skipped_unsafe_input",
                guardrail_reason=safety_decision.reason,
                latency_ms={
                    "stt": 0.0,
                    "guardrail_in": input_guardrail_ms,
                    "retrieval": 0.0,
                    "generation": 0.0,
                    "guardrail_out": 0.0,
                    "total": total_ms,
                },
                retrieved_context=[],
            )

        retrieval_start = perf_counter()
        # Request additional candidates because evidence filtering may remove
        # high-ranked dense or generic keyword matches.
        raw_results = self.index.search(normalized_query, top_k=max(top_k * 4, top_k))
        semantic_scores = sorted(
            (result.semantic_score for result in raw_results if result.semantic_score is not None),
            reverse=True,
        )
        best_semantic_score = semantic_scores[0] if semantic_scores else None
        semantic_margin = (
            semantic_scores[0] - semantic_scores[1]
            if len(semantic_scores) >= 2
            else float("inf")
        )
        results = [
            result
            for result in raw_results
            if _has_sufficient_evidence(
                query_terms,
                result,
                self.minimum_lexical_coverage,
                self.minimum_semantic_similarity,
                self.minimum_semantic_margin,
                best_semantic_score,
                semantic_margin,
            )
        ][:top_k]
        retrieval_ms = (perf_counter() - retrieval_start) * 1000

        confidence = _confidence(results)
        top_retrieval_score = (
            results[0].semantic_score
            if results and results[0].semantic_score is not None
            else (results[0].dense_score if results else -1.0)
        )
        grounding_start = perf_counter()
        refusal_floor = self.minimum_semantic_similarity if self.index.semantic_enabled else self.minimum_similarity
        refused = not results or top_retrieval_score < refusal_floor
        citations: list[str] = []
        context: list[dict[str, object]] = []
        generation_status = "not_requested"
        generation_ms = 0.0
        guardrail_reason: str | None = None

        if refused:
            answer = "I do not have enough evidence in the indexed competition dataset to answer that."
            path_taken = "refusal"
            generation_status = "skipped_insufficient_evidence"
            guardrail_reason = "insufficient_grounding"
        else:
            context = [result.to_dict() for result in results]
            citations = [result.chunk.chunk_id for result in results]
            path_taken = "verified_retrieval"
            answer = (
                "Retrieved evidence is available below. "
                "Answer generation was not requested."
            )

            if generate:
                generation_start = perf_counter()
                try:
                    if self.generator is None:
                        raise ProviderConfigurationError("No answer-generation provider was configured.")
                    generated = self.generator.generate(normalized_query, results)
                    answer = generated.answer
                    citations = generated.cited_chunk_ids
                    generation_status = "complete"
                    path_taken = "verified_retrieval_generation"
                except ProviderConfigurationError:
                    answer = "Answer generation is unavailable because the provider is not configured."
                    citations = []
                    refused = True
                    path_taken = "generation_unavailable"
                    generation_status = "unavailable"
                    guardrail_reason = "provider_unavailable"
                except ProviderRequestError:
                    answer = "I could not produce a verified grounded answer from the generation provider."
                    citations = []
                    refused = True
                    path_taken = "generation_failed_closed"
                    generation_status = "failed_closed"
                    guardrail_reason = "provider_request_failed"
                finally:
                    generation_ms = (perf_counter() - generation_start) * 1000

        grounding_ms = (perf_counter() - grounding_start) * 1000
        total_ms = (perf_counter() - overall_start) * 1000

        return QueryResponse(
            answer=answer,
            cited_chunk_ids=citations,
            confidence=confidence,
            path_taken=path_taken,
            refused=refused,
            generation_status=generation_status,
            guardrail_reason=guardrail_reason,
            latency_ms={
                "stt": 0.0,
                "guardrail_in": input_guardrail_ms,
                "retrieval": retrieval_ms,
                "generation": generation_ms,
                "guardrail_out": grounding_ms,
                "total": total_ms,
            },
            retrieved_context=context,
        )
