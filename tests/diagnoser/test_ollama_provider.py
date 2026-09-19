"""Offline tests for the Ollama adapter — a fake HTTP transport injected at
construction time. None of these tests make a real network call or require
a running Ollama server.
"""

import urllib.error

import pytest

from renacir.diagnoser.provider import LLMRequest
from renacir.diagnoser.providers.ollama import OllamaProvider, fetch_model_metadata


def _request(**overrides):
    kwargs = dict(
        system_prompt="sys",
        user_prompt="user text",
        model="qwen2.5-coder:7b",
        temperature=0.0,
        max_tokens=512,
    )
    kwargs.update(overrides)
    return LLMRequest(**kwargs)


class _RecordingPost:
    def __init__(self, response=None, exception=None):
        self._response = response
        self._exception = exception
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url, payload):
        self.calls.append((url, payload))
        if self._exception is not None:
            raise self._exception
        return self._response


def test_generate_maps_request_fields_to_ollama_chat_payload():
    post = _RecordingPost(
        response={
            "message": {"role": "assistant", "content": "hi"},
            "prompt_eval_count": 1,
            "eval_count": 1,
        }
    )
    provider = OllamaProvider(http_post=post)

    provider.generate(_request(model="qwen2.5-coder:7b", temperature=0.2, max_tokens=77))

    assert len(post.calls) == 1
    url, payload = post.calls[0]
    assert url.endswith("/api/chat")
    assert payload["model"] == "qwen2.5-coder:7b"
    assert payload["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user text"},
    ]
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == 0.2
    assert payload["options"]["num_predict"] == 77


def test_generate_is_model_family_agnostic():
    """Nothing about the provider changes behavior based on which model
    string is requested -- swapping the model tag requires no code change."""
    post = _RecordingPost(response={"message": {"content": "ok"}})
    provider = OllamaProvider(http_post=post)

    provider.generate(_request(model="some-completely-different-model:latest"))

    assert post.calls[0][1]["model"] == "some-completely-different-model:latest"


def test_generate_extracts_raw_text_and_token_usage():
    post = _RecordingPost(
        response={
            "message": {"role": "assistant", "content": "the diagnosis text"},
            "prompt_eval_count": 123,
            "eval_count": 45,
        }
    )
    provider = OllamaProvider(http_post=post)

    response = provider.generate(_request())

    assert response.raw_text == "the diagnosis text"
    assert response.input_tokens == 123
    assert response.output_tokens == 45
    assert response.provider_error is None


def test_generate_records_latency():
    post = _RecordingPost(response={"message": {"content": "x"}})
    provider = OllamaProvider(http_post=post)

    response = provider.generate(_request())

    assert response.latency_seconds is not None
    assert response.latency_seconds >= 0.0


def test_generate_maps_transport_error_to_provider_error_without_raising():
    post = _RecordingPost(exception=urllib.error.URLError("connection refused"))
    provider = OllamaProvider(http_post=post)

    response = provider.generate(_request())

    assert response.raw_text is None
    assert response.provider_error is not None
    assert "connection refused" in response.provider_error


def test_generate_maps_ollama_error_payload_to_provider_error():
    """Ollama reports errors (e.g. model not found) as a 200 response body
    with an "error" key, not always as an HTTP error -- must be mapped
    the same way as a transport-level failure."""
    post = _RecordingPost(response={"error": "model 'nonexistent:1b' not found"})
    provider = OllamaProvider(http_post=post)

    response = provider.generate(_request(model="nonexistent:1b"))

    assert response.raw_text is None
    assert response.provider_error is not None
    assert "not found" in response.provider_error


def test_generate_called_exactly_once_no_retry_on_error():
    post = _RecordingPost(exception=urllib.error.URLError("boom"))
    provider = OllamaProvider(http_post=post)

    provider.generate(_request())

    assert len(post.calls) == 1


def test_non_transport_error_is_not_swallowed():
    post = _RecordingPost(exception=TypeError("unexpected"))
    provider = OllamaProvider(http_post=post)

    with pytest.raises(TypeError):
        provider.generate(_request())


def test_fetch_model_metadata_extracts_generic_fields():
    def fake_get(url):
        assert url.endswith("/api/tags")
        return {
            "models": [
                {
                    "name": "qwen2.5-coder:7b",
                    "digest": "dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364",
                    "details": {
                        "family": "qwen2",
                        "quantization_level": "Q4_K_M",
                        "parameter_size": "7.6B",
                        "context_length": 32768,
                    },
                }
            ]
        }

    metadata = fetch_model_metadata("qwen2.5-coder:7b", http_get=fake_get)

    assert metadata["model"] == "qwen2.5-coder:7b"
    assert metadata["digest"] == "dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364"
    assert metadata["family"] == "qwen2"
    assert metadata["quantization"] == "Q4_K_M"
    assert metadata["parameter_size"] == "7.6B"
    assert metadata["context_length"] == "32768"


def test_fetch_model_metadata_is_model_family_agnostic():
    """A completely different model family produces metadata via the exact
    same generic field lookups -- no branch anywhere checks for a specific
    family name."""

    def fake_get(url):
        return {
            "models": [
                {
                    "name": "llama3.1:8b",
                    "digest": "somedigest123",
                    "details": {
                        "family": "llama",
                        "quantization_level": "Q4_0",
                        "parameter_size": "8.0B",
                        "context_length": 8192,
                    },
                }
            ]
        }

    metadata = fetch_model_metadata("llama3.1:8b", http_get=fake_get)

    assert metadata["family"] == "llama"
    assert metadata["quantization"] == "Q4_0"


def test_fetch_model_metadata_returns_empty_dict_when_model_not_found():
    metadata = fetch_model_metadata("not-installed:1b", http_get=lambda url: {"models": []})
    assert metadata == {}


def test_fetch_model_metadata_returns_empty_dict_on_transport_error():
    def fake_get(url):
        raise urllib.error.URLError("down")

    metadata = fetch_model_metadata("qwen2.5-coder:7b", http_get=fake_get)
    assert metadata == {}
