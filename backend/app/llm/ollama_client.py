"""
llm/ollama_client.py

Generic Ollama HTTP client (Master Specification Section 7: LLM
Reliability).

This is the ONLY place in the codebase that knows how to talk to
Ollama over HTTP. It has no knowledge of quizzes, reflections, question
formats, or any domain concept — it accepts a prompt string and returns
a response string, or raises OllamaGenerationError uniformly for any
failure. Domain-specific providers (OllamaQuizProvider,
OllamaReflectionProvider — Modules 2/3) build prompts and parse
responses; this module never does either.

Model-agnostic by design: the model name is read from
settings.OLLAMA_MODEL (frozen, Phase 3) at call time. No model name is
ever hardcoded here or anywhere else — changing OLLAMA_MODEL in .env is
the only way to change which model is used, and this file requires no
edit to do so.

Timeout: exactly settings.OLLAMA_TIMEOUT_SECONDS (15, per spec Section
7) is applied to every request. A timeout is treated identically to any
other failure — both raise OllamaGenerationError, letting the caller's
fallback logic handle it uniformly.
"""

from __future__ import annotations

import httpx

from app.core.config import settings


class OllamaGenerationError(Exception):
    """
    Raised for ANY failure calling Ollama: connection refused, timeout,
    non-200 response, or a malformed/empty response body. Callers
    (provider classes) should catch this single exception type and
    fall back to the template path — they never need to distinguish
    the underlying cause.
    """


def generate(prompt: str) -> str:
    """
    Send a prompt to the locally-running Ollama server and return the
    raw generated text.

    Raises OllamaGenerationError on any failure (network error,
    timeout after settings.OLLAMA_TIMEOUT_SECONDS, non-200 response,
    or a response body missing the expected "response" field).
    """
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }

    try:
        response = httpx.post(
            url,
            json=payload,
            timeout=settings.OLLAMA_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as exc:
        raise OllamaGenerationError(
            f"Ollama request timed out after {settings.OLLAMA_TIMEOUT_SECONDS}s."
        ) from exc
    except httpx.RequestError as exc:
        raise OllamaGenerationError(f"Ollama request failed: {exc}") from exc

    if response.status_code != 200:
        raise OllamaGenerationError(
            f"Ollama returned HTTP {response.status_code}: {response.text[:200]}"
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise OllamaGenerationError("Ollama response was not valid JSON.") from exc

    text = body.get("response")
    if not text or not isinstance(text, str):
        raise OllamaGenerationError(
            "Ollama response did not contain a non-empty 'response' field."
        )

    return text
