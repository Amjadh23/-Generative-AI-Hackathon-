"""Thin Ollama HTTP client.

Uses the ``/api/chat`` endpoint with optional structured-JSON output
(``format="json"``). No third-party SDK so the only runtime dep is the
standard library + ``urllib`` for portability.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class LLMError(RuntimeError):
    """Raised when the LLM call fails (network, timeout, malformed response)."""


@dataclass(frozen=True)
class LLMSettings:
    host: str
    model: str
    timeout_seconds: float
    temperature: float


def get_settings() -> LLMSettings:
    return LLMSettings(
        host=os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
        model=os.environ.get("OLLAMA_MODEL", "llama3.2:3b"),
        timeout_seconds=float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "60")),
        temperature=float(os.environ.get("OLLAMA_TEMPERATURE", "0.2")),
    )


def chat(
    system_prompt: str,
    user_prompt: str,
    *,
    json_mode: bool = False,
    temperature: float | None = None,
) -> str:
    """Call the Ollama chat endpoint and return the assistant's text content.

    Raises :class:`LLMError` for any network / parsing failure so callers can
    fail loud (per project decision to not silently fall back).
    """
    settings = get_settings()
    url = f"{settings.host}/api/chat"
    payload: dict[str, Any] = {
        "model": settings.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": settings.temperature if temperature is None else temperature,
        },
    }
    if json_mode:
        payload["format"] = "json"

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise LLMError(
            f"Could not reach Ollama at {settings.host}. Is `ollama serve` running? ({exc})"
        ) from exc
    except TimeoutError as exc:
        raise LLMError(
            f"Ollama request timed out after {settings.timeout_seconds}s on model {settings.model}."
        ) from exc

    try:
        data = json.loads(raw)
        content = data["message"]["content"]
    except (KeyError, json.JSONDecodeError) as exc:
        raise LLMError(f"Malformed Ollama response: {raw[:200]}") from exc

    if not isinstance(content, str):
        raise LLMError(f"Unexpected content type from Ollama: {type(content).__name__}")
    return content.strip()


def chat_json(system_prompt: str, user_prompt: str, *, temperature: float = 0.0) -> dict[str, Any]:
    """Call the LLM in JSON mode and return the parsed object.

    Useful for structured extraction (visit recap, follow-up emails, etc).
    """
    raw = chat(system_prompt, user_prompt, json_mode=True, temperature=temperature)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM returned non-JSON output: {raw[:200]}") from exc
    if not isinstance(parsed, dict):
        raise LLMError(f"LLM JSON output is not an object: {type(parsed).__name__}")
    return parsed
