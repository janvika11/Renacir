import json

import pytest

from renacir.benchmark.discovery import discover_cases
from renacir.benchmark.reconstruction import is_prepared
from renacir.collector.collector import collect
from renacir.collector.models import CollectorInput
from renacir.diagnoser.diagnoser import diagnose
from renacir.diagnoser.provider import LLMResponse
from renacir.diagnoser.providers.fake import FakeProvider

VALID_DIAGNOSIS_JSON = json.dumps(
    {
        "root_cause_summary": "Off-by-one in the denominator of average()",
        "suspected_files": ["stats.py"],
        "suspected_symbols": ["average"],
        "reasoning_summary": "The failing assertion shows average([2,4,6]) == 6.0, not 4.",
        "diagnosis_confidence": 0.65,
        "insufficient_context": False,
    }
)


def _output(case_id="assertion-average-off-by-one"):
    return collect(CollectorInput(case_id=case_id))


def _diagnose(provider, condition="full_context", case_id="assertion-average-off-by-one"):
    return diagnose(
        case_id,
        _output(case_id),
        condition,
        provider,
        model="test-model",
        temperature=0.0,
        max_tokens=512,
    )


def test_valid_response_parses_successfully():
    provider = FakeProvider(LLMResponse(raw_text=VALID_DIAGNOSIS_JSON))
    record = _diagnose(provider)

    assert record.parse_status == "ok"
    assert record.parsed_diagnosis is not None
    assert record.parsed_diagnosis.suspected_files == ["stats.py"]
    assert record.grounding_violation is False


def test_malformed_json_is_recorded_not_crashed_on():
    provider = FakeProvider(LLMResponse(raw_text="not json at all {{{"))
    record = _diagnose(provider)

    assert record.parse_status == "parse_error"
    assert record.parsed_diagnosis is None
    assert record.raw_response == "not json at all {{{"


def test_schema_invalid_json_is_recorded_as_validation_error():
    bad = json.dumps(
        {
            "root_cause_summary": "x",
            "suspected_files": [],
            "suspected_symbols": [],
            "reasoning_summary": "y",
            "diagnosis_confidence": 5.0,  # out of bounds
            "insufficient_context": False,
        }
    )
    provider = FakeProvider(LLMResponse(raw_text=bad))
    record = _diagnose(provider)

    assert record.parse_status == "validation_error"
    assert record.parsed_diagnosis is None
    assert record.raw_response == bad


def test_provider_error_is_recorded():
    provider = FakeProvider(LLMResponse(raw_text=None, provider_error="rate limited"))
    record = _diagnose(provider)

    assert record.parse_status == "provider_error"
    assert record.provider_error == "rate limited"
    assert record.parsed_diagnosis is None


def test_provider_is_called_exactly_once_no_retry():
    provider = FakeProvider(LLMResponse(raw_text="malformed"))
    _diagnose(provider)
    assert len(provider.calls) == 1

    provider2 = FakeProvider(LLMResponse(raw_text=None, provider_error="boom"))
    _diagnose(provider2)
    assert len(provider2.calls) == 1


def test_grounding_violation_detected_for_unseen_file():
    bad_grounding = json.dumps(
        {
            "root_cause_summary": "x",
            "suspected_files": ["totally/unseen/file.py"],
            "suspected_symbols": [],
            "reasoning_summary": "y",
            "diagnosis_confidence": 0.5,
            "insufficient_context": False,
        }
    )
    provider = FakeProvider(LLMResponse(raw_text=bad_grounding))
    record = _diagnose(provider)

    assert record.parse_status == "ok"
    assert record.grounding_violation is True


def test_grounding_valid_for_visible_file():
    provider = FakeProvider(LLMResponse(raw_text=VALID_DIAGNOSIS_JSON))
    record = _diagnose(provider)
    assert record.grounding_violation is False


def test_insufficient_context_path_does_not_require_files():
    insufficient = json.dumps(
        {
            "root_cause_summary": "Not enough evidence to localize a specific defect.",
            "suspected_files": [],
            "suspected_symbols": [],
            "reasoning_summary": "No source context was available.",
            "diagnosis_confidence": 0.1,
            "insufficient_context": True,
        }
    )
    provider = FakeProvider(LLMResponse(raw_text=insufficient))
    record = _diagnose(provider, condition="failure_output_only")

    assert record.parse_status == "ok"
    assert record.parsed_diagnosis.insufficient_context is True
    assert record.grounding_violation is False


def test_run_record_completeness():
    provider = FakeProvider(
        LLMResponse(
            raw_text=VALID_DIAGNOSIS_JSON, input_tokens=123, output_tokens=45, latency_seconds=0.9
        )
    )
    record = _diagnose(provider)

    assert record.case_id == "assertion-average-off-by-one"
    assert record.condition == "full_context"
    assert record.run_id
    assert record.provider == "FakeProvider"
    assert record.model == "test-model"
    assert record.prompt_version == "diagnoser-v1"
    assert record.temperature == 0.0
    assert record.max_tokens == 512
    assert record.timestamp is not None
    assert record.renacir_commit  # non-empty, "unknown" is an acceptable fallback
    assert len(record.input_fingerprint) == 64
    assert record.rendered_system_prompt
    assert record.rendered_user_prompt
    assert record.raw_response == VALID_DIAGNOSIS_JSON
    assert record.input_tokens == 123
    assert record.output_tokens == 45
    assert record.latency_seconds == 0.9


def test_two_conditions_produce_different_selected_context_visibility():
    output = _output("assertion-average-off-by-one")
    provider = FakeProvider(
        [LLMResponse(raw_text=VALID_DIAGNOSIS_JSON), LLMResponse(raw_text=VALID_DIAGNOSIS_JSON)]
    )

    failure_only_record = diagnose(
        "assertion-average-off-by-one",
        output,
        "failure_output_only",
        provider,
        model="m",
        temperature=0.0,
        max_tokens=10,
    )
    full_context_record = diagnose(
        "assertion-average-off-by-one",
        output,
        "full_context",
        provider,
        model="m",
        temperature=0.0,
        max_tokens=10,
    )

    stats_py_source = "def average(nums):"

    assert "SOURCE_FILES: none provided" in failure_only_record.rendered_user_prompt
    assert "SOURCE_FILES:" in full_context_record.rendered_user_prompt
    assert stats_py_source in full_context_record.rendered_user_prompt
    # "stats.py" the bare filename legitimately appears in failure_output_only
    # too (as a substring of "test_stats.py" in stdout/frames) -- what must
    # be absent there is the file's actual CONTENT.
    assert stats_py_source not in failure_only_record.rendered_user_prompt


@pytest.mark.skipif(
    not is_prepared(next(c for c in discover_cases() if c.id == "httpie-custom-host-header")),
    reason="run `python -m renacir.benchmark prepare` first",
)
def test_httpie_custom_host_header_full_context_selected_context_stays_empty():
    output = _output("httpie-custom-host-header")
    assert output.selected_context == []  # Phase 3's own measured behavior, unchanged

    provider = FakeProvider(
        LLMResponse(
            raw_text=json.dumps(
                {
                    "root_cause_summary": "Insufficient evidence to localize a specific file.",
                    "suspected_files": [],
                    "suspected_symbols": [],
                    "reasoning_summary": "No source context was provided beyond failure output.",
                    "diagnosis_confidence": 0.15,
                    "insufficient_context": True,
                }
            )
        )
    )
    record = diagnose(
        "httpie-custom-host-header",
        output,
        "full_context",
        provider,
        model="m",
        temperature=0.0,
        max_tokens=512,
    )

    assert "SOURCE_FILES: none provided" in record.rendered_user_prompt
    assert record.grounding_violation is False
