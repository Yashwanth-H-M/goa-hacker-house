"""Supported competition-language configuration for the multilingual RAG build."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageOption:
    config: str
    display_name: str
    stt_code: str
    validation_parquet: str


SUPPORTED_LANGUAGES: dict[str, LanguageOption] = {
    "hi": LanguageOption(
        config="hi",
        display_name="Hindi",
        stt_code="hi-IN",
        validation_parquet="validation/hinval.parquet",
    ),
    "kn": LanguageOption(
        config="kn",
        display_name="Kannada",
        stt_code="kn-IN",
        validation_parquet="validation/kanval.parquet",
    ),
    "te": LanguageOption(
        config="te",
        display_name="Telugu",
        stt_code="te-IN",
        validation_parquet="validation/telval.parquet",
    ),
}
DEFAULT_LANGUAGE_ORDER: tuple[str, ...] = ("hi", "kn", "te")


def require_supported_language(language: str) -> LanguageOption:
    """Return a configured language or raise an actionable validation error."""

    normalized = language.strip().lower()
    try:
        return SUPPORTED_LANGUAGES[normalized]
    except KeyError as exc:
        allowed = ", ".join(DEFAULT_LANGUAGE_ORDER)
        raise ValueError(f"Unsupported language '{language}'. Choose one of: {allowed}.") from exc
