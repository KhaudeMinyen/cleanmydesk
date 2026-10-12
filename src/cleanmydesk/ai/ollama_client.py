"""Talks to Ollama, the free program that runs AI models on this computer.

Ollama runs a small web server on the computer (http://localhost:11434 by
default). This module sends it the conversation and reads the answer back
a few words at a time. It only uses Python's standard library.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass

DEFAULT_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:8b"
CONNECT_TIMEOUT_S = 5
# The first answer can be slow while Ollama loads the model into memory.
ANSWER_TIMEOUT_S = 300


class OllamaError(Exception):
    """Something went wrong talking to Ollama. The message is for the user."""


@dataclass
class ChatMessage:
    role: str  # "system", "user" or "assistant"
    content: str


def default_url() -> str:
    """Ollama's address, from OLLAMA_HOST if it is set (as Ollama itself does)."""
    host = os.environ.get("OLLAMA_HOST", "").strip()
    if not host:
        return DEFAULT_URL
    if "://" not in host:
        host = "http://" + host
    if host.count(":") < 2:  # no port given
        host += ":11434"
    return host.rstrip("/")


class OllamaClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or default_url()).rstrip("/")

    def list_models(self) -> list[str]:
        """Names of the models that have been downloaded with `ollama pull`."""
        data = self._get_json("/api/tags", CONNECT_TIMEOUT_S)
        return sorted(model["name"] for model in data.get("models", []))

    def stream_chat(self, model: str, messages: list[ChatMessage]) -> Iterator[str]:
        """Send the conversation and yield the answer piece by piece."""
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": True,
            }
        ).encode()
        request = urllib.request.Request(
            self.base_url + "/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response = self._open(request, ANSWER_TIMEOUT_S, model)
        with response:
            while True:
                try:
                    raw_line = response.readline()
                except OSError as exc:  # includes timeouts
                    raise OllamaError("Ollama stopped answering partway through.") from exc
                if not raw_line:
                    return
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise OllamaError("Ollama sent a reply this app could not read.") from exc
                if "error" in chunk:
                    raise OllamaError(f"Ollama reported an error: {chunk['error']}")
                text = chunk.get("message", {}).get("content", "")
                if text:
                    yield text
                if chunk.get("done"):
                    return

    def _get_json(self, path: str, timeout: float) -> dict:
        with self._open(urllib.request.Request(self.base_url + path), timeout) as response:
            try:
                return json.loads(response.read())
            except json.JSONDecodeError as exc:
                raise OllamaError("Ollama sent a reply this app could not read.") from exc

    def _open(self, request: urllib.request.Request, timeout: float, model: str | None = None):
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            detail = _error_detail(exc)
            if exc.code == 404 and model:
                raise OllamaError(
                    f'The model "{model}" is not downloaded yet. '
                    f"In a terminal, run `ollama pull {model}`, then try again."
                ) from exc
            raise OllamaError(f"Ollama answered with an error ({exc.code}): {detail}") from exc
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
            raise OllamaError(
                f"Could not reach Ollama at {self.base_url}. Make sure Ollama is "
                "installed (from https://ollama.com) and running, and that you have "
                f"downloaded a model, for example with `ollama pull {DEFAULT_MODEL}`."
            ) from exc


def _error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        return json.loads(exc.read()).get("error", exc.reason)
    except (json.JSONDecodeError, OSError, AttributeError):
        return str(exc.reason)
