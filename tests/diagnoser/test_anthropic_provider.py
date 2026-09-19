"""Offline tests for the Anthropic adapter — mocks/fakes at the SDK
boundary only. None of these tests make a network call or require
ANTHROPIC_API_KEY to be set.
"""

import anthropic
import httpx2
import pytest

from renacir.diagnoser.provider import LLMRequest
from renacir.diagnoser.providers.anthropic import AnthropicConfigurationError, AnthropicProvider


class _FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeUsage:
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeMessage:
    def __init__(self, text, input_tokens=42, output_tokens=17):
        self.content = [_FakeTextBlock(text)]
        self.usage = _FakeUsage(input_tokens, output_tokens)


class _FakeMessagesResource:
    def __init__(self, response=None, exception=None):
        self._response = response
        self._exception = exception
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._exception is not None:
            raise self._exception
        return self._response


class _FakeAnthropicClient:
    def __init__(self, messages_resource):
        self.messages = messages_resource


def _request(**overrides):
    kwargs = dict(
        system_prompt="sys",
        user_prompt="user text",
        model="claude-fake-1",
        temperature=0.0,
        max_tokens=512,
    )
    kwargs.update(overrides)
    return LLMRequest(**kwargs)


def test_missing_api_key_raises_configuration_error():
    with pytest.raises(AnthropicConfigurationError):
        AnthropicProvider(api_key="")


def test_missing_api_key_raises_before_any_client_construction():
    """No SDK client should ever be built when the key is missing."""
    with pytest.raises(AnthropicConfigurationError):
        AnthropicProvider(api_key="")
    # If construction had proceeded, a real anthropic.Anthropic() with an
    # empty key would itself likely raise a different, less clear error --
    # the point is our own check fires first, deterministically.


def test_generate_maps_request_fields_to_anthropic_call():
    resource = _FakeMessagesResource(response=_FakeMessage("hello"))
    provider = AnthropicProvider(api_key="fake-key", client=_FakeAnthropicClient(resource))

    provider.generate(_request(model="claude-fake-1", temperature=0.3, max_tokens=99))

    assert len(resource.calls) == 1
    call = resource.calls[0]
    assert call["model"] == "claude-fake-1"
    assert call["system"] == "sys"
    assert call["messages"] == [{"role": "user", "content": "user text"}]
    assert call["temperature"] == 0.3
    assert call["max_tokens"] == 99


def test_generate_extracts_raw_text_and_token_usage():
    resource = _FakeMessagesResource(
        response=_FakeMessage("the diagnosis text", input_tokens=100, output_tokens=55)
    )
    provider = AnthropicProvider(api_key="fake-key", client=_FakeAnthropicClient(resource))

    response = provider.generate(_request())

    assert response.raw_text == "the diagnosis text"
    assert response.input_tokens == 100
    assert response.output_tokens == 55
    assert response.provider_error is None


def test_generate_records_latency():
    resource = _FakeMessagesResource(response=_FakeMessage("x"))
    provider = AnthropicProvider(api_key="fake-key", client=_FakeAnthropicClient(resource))

    response = provider.generate(_request())

    assert response.latency_seconds is not None
    assert response.latency_seconds >= 0.0


def test_generate_maps_api_error_to_provider_error_without_raising():
    fake_request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.APIConnectionError(message="connection failed", request=fake_request)
    resource = _FakeMessagesResource(exception=error)
    provider = AnthropicProvider(api_key="fake-key", client=_FakeAnthropicClient(resource))

    response = provider.generate(_request())

    assert response.raw_text is None
    assert response.provider_error is not None
    assert "connection failed" in response.provider_error
    assert response.input_tokens is None
    assert response.output_tokens is None


def test_generate_called_exactly_once_no_retry_on_error():
    fake_request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.APIConnectionError(message="boom", request=fake_request)
    resource = _FakeMessagesResource(exception=error)
    provider = AnthropicProvider(api_key="fake-key", client=_FakeAnthropicClient(resource))

    provider.generate(_request())

    assert len(resource.calls) == 1


def test_non_api_error_is_not_swallowed():
    """Only anthropic.APIError is mapped to provider_error -- a genuine bug
    (e.g. a TypeError in our own code) must propagate, not be hidden as if
    it were a provider-side failure."""
    resource = _FakeMessagesResource(exception=TypeError("unexpected"))
    provider = AnthropicProvider(api_key="fake-key", client=_FakeAnthropicClient(resource))

    with pytest.raises(TypeError):
        provider.generate(_request())


def test_real_client_construction_disables_sdk_internal_retries():
    """The Anthropic SDK defaults to max_retries=2 internally -- verify our
    adapter explicitly overrides this to 0 when it builds a real client
    (no network call made; only construction is inspected)."""
    provider = AnthropicProvider(api_key="fake-key-for-construction-only")
    assert provider._client.max_retries == 0


def test_api_key_never_appears_on_the_provider_object_as_plaintext_elsewhere():
    """Weak but cheap structural check: the provider doesn't stash the raw
    key on an attribute with an obvious name other than inside the SDK
    client it constructs."""
    provider = AnthropicProvider(api_key="sk-super-secret-marker-value")
    assert not hasattr(provider, "api_key")
    assert not hasattr(provider, "_api_key")


def test_api_key_never_appears_in_a_full_diagnose_run_record():
    """End-to-end: run the actual renacir.diagnoser.diagnoser.diagnose()
    orchestration with an AnthropicProvider (fake SDK client), and confirm
    the API key string never appears anywhere in the resulting
    DiagnosisRunRecord's serialized JSON -- covering the rendered prompt,
    the fingerprint, and every other field."""
    import json

    from renacir.benchmark.discovery import discover_cases
    from renacir.collector.collector import collect
    from renacir.collector.models import CollectorInput
    from renacir.diagnoser.diagnoser import diagnose

    secret_marker = "sk-ant-do-not-leak-this-marker-0123456789"
    payload = json.dumps(
        {
            "root_cause_summary": "x",
            "suspected_files": [],
            "suspected_symbols": [],
            "reasoning_summary": "y",
            "diagnosis_confidence": 0.5,
            "insufficient_context": False,
        }
    )
    resource = _FakeMessagesResource(response=_FakeMessage(payload))
    provider = AnthropicProvider(api_key=secret_marker, client=_FakeAnthropicClient(resource))

    case = next(c for c in discover_cases() if c.id == "assertion-average-off-by-one")
    output = collect(CollectorInput(case_id=case.id))
    record = diagnose(
        case.id,
        output,
        "full_context",
        provider,
        model="claude-fake-1",
        temperature=0.0,
        max_tokens=100,
    )

    serialized = record.model_dump_json()
    assert secret_marker not in serialized
    assert secret_marker not in record.rendered_system_prompt
    assert secret_marker not in record.rendered_user_prompt
    assert secret_marker not in record.input_fingerprint
