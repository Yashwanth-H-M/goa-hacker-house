"""Deterministic input guardrails for the local competition RAG pipeline.

The filter is intentionally narrow and transparent: it blocks clear requests for
violent wrongdoing, self-harm instructions, credential theft, or sexual
exploitation before retrieval or generation. It is a demonstration safeguard,
not a substitute for a production multilingual safety classifier.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class InputGuardrailDecision:
    """Result of a lightweight pre-retrieval safety check."""

    blocked: bool
    reason: str | None = None


# These phrases target requests for instructions or operational assistance, not
# neutral references to a topic in the corpus. The list includes common English,
# Hindi, and Hinglish formulations used in the project demonstration languages.
_HARMFUL_REQUEST_PATTERNS = (
    r"\bhow\s+to\s+(make|build|buy|use)\s+(a\s+)?(bomb|explosive|weapon|poison)\b",
    r"\bhow\s+to\s+(kill|murder|hurt|attack)\b",
    r"\b(hack|steal|phish)\s+(an?\s+)?(account|password|credential|otp)\b",
    r"\bhow\s+to\s+(self[-\s]?harm|commit\s+suicide)\b",
    r"\b(child\s+sexual|sexualize\s+(a\s+)?child)\b",
    r"\b(बम|विस्फोटक|हथियार|ज़हर|जहर)\s+(कैसे|बनाने|बनाऊँ|बनाएं)\b",
    r"\b(हत्या|मारना|हमला)\s+(कैसे|करना|करूँ)\b",
    r"\b(पासवर्ड|ओटीपी|खाता)\s+(चुराना|हैक|हैक करना)\b",
    r"\b(आत्महत्या|खुदकुशी)\s+(कैसे|करना|करूँ)\b",
)

_COMPILED_PATTERNS = tuple(re.compile(pattern, flags=re.IGNORECASE) for pattern in _HARMFUL_REQUEST_PATTERNS)


def check_input_safety(text: str) -> InputGuardrailDecision:
    """Block clear unsafe or abusive instruction-seeking before retrieval.

    A deterministic decision is deliberately kept inspectable for the demo and
    can be replaced later with a calibrated multilingual moderation provider.
    """

    normalized = " ".join(text.split())
    if any(pattern.search(normalized) for pattern in _COMPILED_PATTERNS):
        return InputGuardrailDecision(blocked=True, reason="unsafe_instruction_request")
    return InputGuardrailDecision(blocked=False)


UNSAFE_INPUT_REFUSAL = (
    "I can’t help with unsafe or harmful instructions. "
    "Please ask an appropriate question that can be answered from the indexed dataset."
)
