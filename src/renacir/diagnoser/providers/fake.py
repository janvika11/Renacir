"""FakeProvider — deterministic testing infrastructure, not an experimental
baseline. Never makes a network call; never imports an LLM SDK. Configured
at construction time with the exact `LLMResponse`(s) to return, so tests can
exercise valid output, malformed JSON, schema-invalid JSON, a provider
error, and token/latency metadata deterministically.
"""

from renacir.diagnoser.provider import LLMRequest, LLMResponse


class FakeProvider:
    def __init__(self, response: LLMResponse | list[LLMResponse]):
        self._responses = response if isinstance(response, list) else [response]
        self._index = 0
        self.calls: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        response = self._responses[min(self._index, len(self._responses) - 1)]
        self._index += 1
        return response
