"""External-provider adapters with explicit, fail-closed grounding behavior."""

from __future__ import annotations

from dataclasses import dataclass
import json
import mimetypes
from pathlib import Path
from typing import Any, Iterable
from urllib import error, request
import time
import uuid

from src.retrieval import SearchResult


class ProviderConfigurationError(RuntimeError):
    """Raised when a requested provider is not configured locally."""


class ProviderRequestError(RuntimeError):
    """Raised when a provider rejects a request or returns an unusable response."""


@dataclass(frozen=True)
class Transcription:
    transcript: str
    language_code: str | None
    request_id: str | None


def _multipart_body(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    fields: dict[str, str],
) -> tuple[bytes, str]:
    """Build a multipart request without an additional dependency."""

    boundary = f"----HHGoaRag{uuid.uuid4().hex}"
    body = bytearray()
    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    )
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
    body.extend(file_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), boundary


def _read_json_response(
    http_request: request.Request,
    timeout_seconds: float = 35.0,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Call a provider with bounded retries for transient failures.

    The retry policy covers common provider overload and transport failures. It
    intentionally avoids embedding remote response bodies in local errors so a
    provider cannot reflect user prompts or other sensitive content into logs.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    retryable_statuses = {429, 500, 502, 503, 504}
    for attempt in range(max_attempts):
        try:
            with request.urlopen(http_request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ProviderRequestError("Provider returned a non-JSON response.") from exc
        except error.HTTPError as exc:
            if exc.code not in retryable_statuses or attempt == max_attempts - 1:
                raise ProviderRequestError(f"Provider returned HTTP {exc.code}.") from exc
        except error.URLError as exc:
            if attempt == max_attempts - 1:
                raise ProviderRequestError("Provider request failed due to a network error.") from exc

        # 250 ms, then 500 ms: enough to ride out a transient failure without
        # turning an interactive request into an unbounded wait.
        time.sleep(0.25 * (2**attempt))

    raise ProviderRequestError("Provider request failed after bounded retries.")


class SarvamTranscriber:
    """Sarvam REST transcription for short browser-recorded audio."""

    endpoint = "https://api.sarvam.ai/speech-to-text"

    def __init__(self, api_key: str | None, model: str = "saaras:v3") -> None:
        self.api_key = api_key
        self.model = model

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "recording.webm",
        content_type: str = "audio/webm",
        language_code: str = "unknown",
    ) -> Transcription:
        if not self.api_key:
            raise ProviderConfigurationError(
                "Sarvam is not configured. Add SARVAM_API_KEY to the local .env file."
            )
        if not audio_bytes:
            raise ValueError("Audio upload cannot be empty.")

        body, boundary = _multipart_body(
            audio_bytes,
            filename=filename,
            content_type=content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
            fields={
                "model": self.model,
                "mode": "transcribe",
                "language_code": language_code,
                "with_timestamps": "false",
            },
        )
        response = _read_json_response(
            request.Request(
                self.endpoint,
                data=body,
                headers={
                    "api-subscription-key": self.api_key,
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Accept": "application/json",
                },
                method="POST",
            )
        )
        transcript = response.get("transcript")
        if not isinstance(transcript, str) or not transcript.strip():
            raise ProviderRequestError("Sarvam returned no usable transcript.")
        return Transcription(
            transcript=transcript.strip(),
            language_code=response.get("language_code") if isinstance(response.get("language_code"), str) else None,
            request_id=response.get("request_id") if isinstance(response.get("request_id"), str) else None,
        )


@dataclass(frozen=True)
class GroundedAnswer:
    answer: str
    cited_chunk_ids: list[str]


def _context_block(results: Iterable[SearchResult]) -> str:
    return "\n\n".join(
        f"[chunk_id={item.chunk.chunk_id}]\n{item.chunk.text}" for item in results
    )


class OpenAICompatibleGenerator:
    """Chat-completions adapter that enforces a JSON answer/citation contract."""

    def __init__(self, api_key: str | None, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def generate(self, question: str, results: list[SearchResult]) -> GroundedAnswer:
        if not self.api_key:
            raise ProviderConfigurationError(
                "Answer generation is not configured. Add OPENAI_API_KEY to the local .env file."
            )
        if not results:
            raise ProviderRequestError("Generation requires at least one retrieved source chunk.")

        permitted_ids = [item.chunk.chunk_id for item in results]
        schema = {
            "name": "grounded_rag_answer",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "answer": {"type": "string"},
                    "cited_chunk_ids": {
                        "type": "array",
                        "items": {"type": "string", "enum": permitted_ids},
                        "minItems": 1,
                    },
                },
                "required": ["answer", "cited_chunk_ids"],
            },
        }
        system_message = (
            "Answer only from the supplied retrieved context. Do not use outside knowledge. "
            "If the context cannot answer the question, write exactly: "
            "'I do not have enough information in the retrieved context to answer that.' "
            "Cite every source chunk used by its exact chunk ID."
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": f"Question:\n{question}\n\nRetrieved context:\n{_context_block(results)}",
                },
            ],
            "response_format": {"type": "json_schema", "json_schema": schema},
            "temperature": 0,
        }
        http_request = request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        response = _read_json_response(http_request, timeout_seconds=45.0)
        try:
            raw_content = response["choices"][0]["message"]["content"]
            parsed = json.loads(raw_content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderRequestError("The generation provider returned an invalid structured response.") from exc

        answer = parsed.get("answer")
        cited_chunk_ids = parsed.get("cited_chunk_ids")
        if not isinstance(answer, str) or not answer.strip() or not isinstance(cited_chunk_ids, list):
            raise ProviderRequestError("The generation response missed required answer or citation fields.")
        if not cited_chunk_ids or any(chunk_id not in permitted_ids for chunk_id in cited_chunk_ids):
            raise ProviderRequestError("The generation response cited an unknown or missing source chunk.")
        return GroundedAnswer(answer=answer.strip(), cited_chunk_ids=list(cited_chunk_ids))
