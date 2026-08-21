"""Run the local browser interface and multilingual API for the HH Goa RAG application."""

from __future__ import annotations

import argparse
import gc
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os

# Limit CPU worker thread pool memory overhead for 512MB RAM cloud environments
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.config import DEFAULT_SETTINGS, Settings
from src.languages import DEFAULT_LANGUAGE_ORDER, LanguageOption, require_supported_language
from src.pipeline import TextRAGPipeline
from src.providers import OpenAICompatibleGenerator, ProviderConfigurationError, ProviderRequestError, SarvamTranscriber
from src.retrieval import HybridIndex

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = PROJECT_ROOT / "web"
MAX_AUDIO_BYTES = 20 * 1024 * 1024


def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _serve_file(handler: BaseHTTPRequestHandler, filename: str, content_type: str) -> None:
    source = WEB_ROOT / filename
    if not source.exists():
        handler.send_error(HTTPStatus.NOT_FOUND)
        return
    payload = source.read_bytes()
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(payload)


def load_language_indexes(index_dir: str | Path) -> dict[str, HybridIndex]:
    """Load every available selected-language index from an index root.

    A legacy single-index directory is exposed as Hindi so the existing local
    fixture remains usable until the multilingual indexes finish downloading.
    """

    root = Path(index_dir)
    indexes: dict[str, HybridIndex] = {}
    for language in DEFAULT_LANGUAGE_ORDER:
        candidate = root / language
        if (candidate / "index.json").exists():
            indexes[language] = HybridIndex.load(candidate)
    if indexes:
        return indexes
    if (root / "index.json").exists():
        return {"hi": HybridIndex.load(root)}
    raise FileNotFoundError(
        f"No index found at {root}. Expected index.json or language subdirectories such as hi/index.json."
    )


def make_handler(indexes: dict[str, HybridIndex], settings: Settings) -> type[BaseHTTPRequestHandler]:
    generator = OpenAICompatibleGenerator(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
    )
    transcriber = SarvamTranscriber(api_key=settings.sarvam_api_key, model=settings.sarvam_model)
    pipelines = {
        language: TextRAGPipeline(
            index=index,
            minimum_similarity=settings.minimum_similarity,
            minimum_semantic_similarity=settings.minimum_semantic_similarity,
            minimum_semantic_margin=settings.minimum_semantic_margin,
            generator=generator,
        )
        for language, index in indexes.items()
    }

    def selected_language(value: Any) -> tuple[LanguageOption, TextRAGPipeline]:
        requested = str(value or DEFAULT_LANGUAGE_ORDER[0])
        option = require_supported_language(requested)
        try:
            return option, pipelines[option.config]
        except KeyError as exc:
            available = ", ".join(pipelines)
            raise ValueError(f"The {option.display_name} index is not ready. Available indexes: {available}.") from exc

    class RAGRequestHandler(BaseHTTPRequestHandler):
        server_version = "HHGoaRAG/0.2"

        def log_message(self, format: str, *args: object) -> None:
            # Avoid logging potentially sensitive user questions or transcripts.
            return

        def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()
            self.wfile.write(encoded)

        def _error(self, status: HTTPStatus, message: str) -> None:
            self._json(status, {"error": {"message": message}})

        def _read_body(self) -> bytes:
            content_length = self.headers.get("Content-Length")
            if not content_length:
                raise ValueError("A Content-Length header is required.")
            try:
                size = int(content_length)
            except ValueError as exc:
                raise ValueError("Content-Length must be an integer.") from exc
            if size < 1:
                raise ValueError("Request body cannot be empty.")
            if size > MAX_AUDIO_BYTES:
                raise ValueError("Audio upload exceeds the 20 MB local limit.")
            return self.rfile.read(size)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                _serve_file(self, "index.html", "text/html; charset=utf-8")
            elif path == "/app.css":
                _serve_file(self, "app.css", "text/css; charset=utf-8")
            elif path == "/app.js":
                _serve_file(self, "app.js", "application/javascript; charset=utf-8")
            elif path == "/api/health":
                language_status = {
                    language: {
                        "display_name": require_supported_language(language).display_name,
                        "chunks": len(index.chunks),
                    }
                    for language, index in indexes.items()
                }
                self._json(
                    HTTPStatus.OK,
                    {
                        "status": "ok",
                        "languages": language_status,
                        "providers": {
                            "sarvam_stt": transcriber.configured,
                            "grounded_generation": generator.configured,
                        },
                    },
                )
            else:
                self._error(HTTPStatus.NOT_FOUND, "Route not found.")

        def do_POST(self) -> None:  # noqa: N802
            parsed_url = urlparse(self.path)
            if parsed_url.path == "/api/query":
                self._handle_text_query()
            elif parsed_url.path == "/api/voice-query":
                self._handle_voice_query(parse_qs(parsed_url.query))
            else:
                self._error(HTTPStatus.NOT_FOUND, "Route not found.")

        def _handle_text_query(self) -> None:
            request_start = perf_counter()
            try:
                raw = self._read_body()
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("JSON request must be an object.")
                question = payload.get("question")
                if not isinstance(question, str):
                    raise ValueError("'question' must be a string.")
                option, pipeline = selected_language(payload.get("language"))
                response = pipeline.query(
                    question,
                    top_k=_safe_int(payload.get("top_k"), settings.default_top_k, 1, 10),
                    generate=_safe_bool(payload.get("generate"), True),
                ).to_dict()
                response["language"] = option.config
                response["language_display_name"] = option.display_name
                response["latency_ms"]["api_end_to_end"] = round((perf_counter() - request_start) * 1000, 3)
                self._json(HTTPStatus.OK, response)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._error(HTTPStatus.BAD_REQUEST, str(exc))
            except Exception:
                self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "The local query pipeline failed unexpectedly.")

        def _handle_voice_query(self, query_parameters: dict[str, list[str]]) -> None:
            request_start = perf_counter()
            try:
                audio = self._read_body()
                filename = self.headers.get("X-Filename", "recording.webm")
                filename = Path(filename).name or "recording.webm"
                content_type = self.headers.get("Content-Type", "audio/webm").split(";", 1)[0]
                option, pipeline = selected_language(query_parameters.get("language", [None])[0])
                stt_start = perf_counter()
                transcription = transcriber.transcribe(
                    audio,
                    filename=filename,
                    content_type=content_type,
                    language_code=option.stt_code,
                )
                stt_ms = (perf_counter() - stt_start) * 1000
                response = pipeline.query(
                    transcription.transcript,
                    top_k=_safe_int(query_parameters.get("top_k", [settings.default_top_k])[0], settings.default_top_k, 1, 10),
                    generate=_safe_bool(query_parameters.get("generate", ["true"])[0], True),
                ).to_dict()
                response["language"] = option.config
                response["language_display_name"] = option.display_name
                response["transcript"] = transcription.transcript
                response["transcription_language_code"] = transcription.language_code
                response["transcription_request_id"] = transcription.request_id
                response["latency_ms"]["stt"] = round(stt_ms, 3)
                response["latency_ms"]["total"] = round(response["latency_ms"]["total"] + stt_ms, 3)
                response["latency_ms"]["api_end_to_end"] = round((perf_counter() - request_start) * 1000, 3)
                self._json(HTTPStatus.OK, response)
            except (ValueError, ProviderConfigurationError) as exc:
                self._error(HTTPStatus.BAD_REQUEST, str(exc))
            except ProviderRequestError as exc:
                self._error(HTTPStatus.BAD_GATEWAY, str(exc))
            except Exception:
                self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "The local voice pipeline failed unexpectedly.")

    return RAGRequestHandler


def run_server(index_dir: str | Path, host: str = "0.0.0.0", port: int = 8000) -> None:
    print(f"Starting Contextline server on {host}:{port} with index path: {index_dir}")
    indexes = load_language_indexes(index_dir)
    print(f"Successfully loaded indexes for languages: {', '.join(indexes)}")
    gc.collect()

    server = ThreadingHTTPServer((host, port), make_handler(indexes, DEFAULT_SETTINGS))
    print(f"HH Goa RAG interface listening live at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    default_index = os.getenv("INDEX_DIR", "index/semantic_multilingual")
    default_host = os.getenv("HOST", "0.0.0.0")
    raw_port = os.getenv("PORT", "8000").strip()
    try:
        default_port = int(raw_port)
    except (TypeError, ValueError):
        default_port = 8000

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", default=default_index, help="Single index directory or multilingual index root.")
    parser.add_argument("--host", default=default_host, help="Host address to bind.")
    parser.add_argument("--port", type=int, default=default_port, help="Port to listen on.")
    return parser


def main() -> None:
    arguments = build_parser().parse_args()
    run_server(arguments.index_dir, arguments.host, arguments.port)


if __name__ == "__main__":
    main()
