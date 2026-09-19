from renacir.diagnoser.provider import LLMRequest, LLMResponse
from renacir.diagnoser.providers.fake import FakeProvider


def _request():
    return LLMRequest(
        system_prompt="sys", user_prompt="user", model="m", temperature=0.0, max_tokens=10
    )


def test_fake_provider_returns_configured_response():
    response = LLMResponse(
        raw_text='{"a": 1}', input_tokens=5, output_tokens=3, latency_seconds=0.5
    )
    provider = FakeProvider(response)

    result = provider.generate(_request())

    assert result == response
    assert len(provider.calls) == 1
    assert provider.calls[0] == _request()


def test_fake_provider_records_every_call():
    provider = FakeProvider(LLMResponse(raw_text="{}"))
    provider.generate(_request())
    provider.generate(_request())
    assert len(provider.calls) == 2


def test_fake_provider_cycles_through_a_list_of_responses():
    responses = [LLMResponse(raw_text="first"), LLMResponse(raw_text="second")]
    provider = FakeProvider(responses)

    assert provider.generate(_request()).raw_text == "first"
    assert provider.generate(_request()).raw_text == "second"
    # exhausted list repeats the last response rather than raising
    assert provider.generate(_request()).raw_text == "second"


def test_fake_provider_never_makes_network_calls():
    """Structural guarantee, not a runtime check: FakeProvider has no
    socket/http/requests/urllib import anywhere."""
    import inspect

    import renacir.diagnoser.providers.fake as fake_module

    source = inspect.getsource(fake_module)
    for forbidden in ("socket", "requests", "urllib", "httpx", "http.client"):
        assert forbidden not in source
