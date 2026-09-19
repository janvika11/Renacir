"""Minimal, provider-neutral LLM interface.

Deliberately small: one request type, one response type, one method — no
retry policy, no rate limiting, no multi-provider routing, no general LLM
framework. A concrete provider adapter (e.g. a future `AnthropicProvider`,
not implemented in this phase) reads its own provider-specific secret (e.g.
`ANTHROPIC_API_KEY`) itself; this module, and everything built on top of it
in `renacir.diagnoser`, never sees an API key or any provider-specific
configuration.
"""

from typing import Protocol

from pydantic import BaseModel


class LLMRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    model: str
    temperature: float
    max_tokens: int


class LLMResponse(BaseModel):
    raw_text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_seconds: float | None = None
    provider_error: str | None = None


class LLMProvider(Protocol):
    def generate(self, request: LLMRequest) -> LLMResponse: ...
