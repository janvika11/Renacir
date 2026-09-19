"""Anthropic Claude provider adapter.

The smallest adapter satisfying `LLMProvider`: translates one `LLMRequest`
into one Anthropic Messages API call and back into one `LLMResponse`. No
retry, no streaming, no tool use, no prompt caching, no batch API, no
provider routing/fallback — see `docs/diagnoser.md`.

The Anthropic SDK client defaults to `max_retries=2` internally (silent
transport-level retries on transient errors). Explicitly overridden to `0`
here — "exactly one call" must hold at the HTTP transport level, not just at
this module's own call site.

Reads its API key ONLY from the caller-supplied `api_key` argument, which
the CLI resolves from the `ANTHROPIC_API_KEY` environment variable (via
`renacir.config.Settings`) — never hardcoded, never logged, never included
in any `LLMRequest`/`LLMResponse`/`DiagnosisRunRecord` field. This module
never reads `os.environ` itself, so it stays fully testable by construction
(pass any string, or inject a fake client) without touching real
configuration.

Does NOT parse `Diagnosis` here — parsing/validation stays in
`renacir.diagnoser.diagnoser`, exactly as for `FakeProvider`.
"""

import time
from typing import Protocol

import anthropic

from renacir.diagnoser.provider import LLMRequest, LLMResponse


class AnthropicConfigurationError(RuntimeError):
    """Raised when the Anthropic API key is missing or empty."""


class _AnthropicClientLike(Protocol):
    messages: object


class AnthropicProvider:
    def __init__(self, api_key: str, client: _AnthropicClientLike | None = None):
        if not api_key:
            raise AnthropicConfigurationError(
                "ANTHROPIC_API_KEY is not set. Set it in the environment or .env "
                "(never pass it as a CLI argument or hardcode it) before using "
                "AnthropicProvider."
            )
        self._client = (
            client if client is not None else anthropic.Anthropic(api_key=api_key, max_retries=0)
        )

    def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        try:
            message = self._client.messages.create(
                model=request.model,
                system=request.system_prompt,
                messages=[{"role": "user", "content": request.user_prompt}],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        except anthropic.APIError as exc:
            return LLMResponse(
                raw_text=None,
                latency_seconds=time.monotonic() - start,
                provider_error=str(exc),
            )

        latency = time.monotonic() - start
        text_blocks = [
            block.text for block in message.content if getattr(block, "type", None) == "text"
        ]
        raw_text = "".join(text_blocks) if text_blocks else None

        usage = getattr(message, "usage", None)
        return LLMResponse(
            raw_text=raw_text,
            input_tokens=getattr(usage, "input_tokens", None) if usage else None,
            output_tokens=getattr(usage, "output_tokens", None) if usage else None,
            latency_seconds=latency,
            provider_error=None,
        )
