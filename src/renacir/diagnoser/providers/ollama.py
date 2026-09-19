"""Ollama local provider adapter.

Model-family-agnostic by construction: the exact model tag (e.g.
"qwen2.5-coder:7b", or any other locally-pulled model) is supplied via
`LLMRequest.model` exactly like every other provider. This module contains
no model-family-specific logic anywhere — pulling and using a different
local model requires no code change here or in the Diagnoser core.

Uses only the Python standard library (`urllib`) to talk to Ollama's local
REST API (`/api/chat`, `/api/tags`) — no SDK, no new dependency. No retry,
no streaming, no tool use. Never downloads a model: this module only ever
calls a model that is already present locally; if it isn't, the call fails
and is reported as a `provider_error`, exactly like any other provider
failure.
"""

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from renacir.diagnoser.provider import LLMRequest, LLMResponse

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"

HttpPost = Callable[[str, dict], dict]
HttpGet = Callable[[str], dict]


def _default_http_post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310 (local-only URL)
        return json.loads(response.read().decode("utf-8"))


def _default_http_get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 (local-only URL)
        return json.loads(response.read().decode("utf-8"))


class OllamaProvider:
    def __init__(self, base_url: str = DEFAULT_OLLAMA_BASE_URL, http_post: HttpPost | None = None):
        self._base_url = base_url.rstrip("/")
        self._http_post = http_post or _default_http_post

    def generate(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        start = time.monotonic()
        try:
            data = self._http_post(f"{self._base_url}/api/chat", payload)
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            OSError,
            ValueError,
        ) as exc:
            return LLMResponse(
                raw_text=None, latency_seconds=time.monotonic() - start, provider_error=str(exc)
            )

        latency = time.monotonic() - start

        if "error" in data:
            return LLMResponse(
                raw_text=None, latency_seconds=latency, provider_error=str(data["error"])
            )

        message = data.get("message") or {}
        raw_text = message.get("content") or None

        return LLMResponse(
            raw_text=raw_text,
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
            latency_seconds=latency,
            provider_error=None,
        )


def fetch_model_metadata(
    model: str, base_url: str = DEFAULT_OLLAMA_BASE_URL, http_get: HttpGet | None = None
) -> dict[str, str]:
    """Evaluator/reproducibility-side helper, deliberately separate from
    `OllamaProvider.generate()` — never called by the Diagnoser core, never
    part of `LLMRequest`/`LLMResponse`. Calls Ollama's `/api/tags` (which
    already reports generically-named fields — `details.family`,
    `.quantization_level`, `.parameter_size`, `.context_length` — no
    model-family-specific key lookup needed) to record exactly which local
    model artifact answered. Returns an empty dict (never a fabricated
    value) if the model isn't found or any field can't be determined.
    """
    get = http_get or _default_http_get
    try:
        data = get(f"{base_url.rstrip('/')}/api/tags")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return {}

    entry = next((m for m in data.get("models", []) if m.get("name") == model), None)
    if entry is None:
        return {}

    details = entry.get("details") or {}
    metadata: dict[str, str] = {"model": model}
    if digest := entry.get("digest"):
        metadata["digest"] = digest
    if family := details.get("family"):
        metadata["family"] = family
    if quant := details.get("quantization_level"):
        metadata["quantization"] = quant
    if params := details.get("parameter_size"):
        metadata["parameter_size"] = params
    if ctx := details.get("context_length"):
        metadata["context_length"] = str(ctx)
    return metadata
