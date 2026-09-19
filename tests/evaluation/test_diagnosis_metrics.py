import json

from renacir.benchmark.discovery import discover_cases
from renacir.collector.collector import collect
from renacir.collector.models import CollectorInput
from renacir.diagnoser.diagnoser import diagnose
from renacir.diagnoser.provider import LLMResponse
from renacir.diagnoser.providers.fake import FakeProvider
from renacir.evaluation.diagnosis import (
    grounding_violation_rate,
    insufficient_context_rate,
    parse_success_rate,
    score_suspected_files,
    summarize_latency_and_tokens,
)


def _case(case_id):
    return next(c for c in discover_cases() if c.id == case_id)


def _record_with(case_id, suspected_files, **overrides):
    output = collect(CollectorInput(case_id=case_id))
    payload = {
        "root_cause_summary": "x",
        "suspected_files": suspected_files,
        "suspected_symbols": [],
        "reasoning_summary": "y",
        "diagnosis_confidence": 0.5,
        "insufficient_context": False,
    }
    payload.update(overrides)
    provider = FakeProvider(LLMResponse(raw_text=json.dumps(payload)))
    return diagnose(
        case_id, output, "full_context", provider, model="m", temperature=0.0, max_tokens=10
    )


def test_suspected_file_score_perfect_recall():
    case = _case("assertion-average-off-by-one")
    record = _record_with(case.id, ["stats.py"])

    score = score_suspected_files(record, case)

    assert score.reference_files_available is True
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.f1 == 1.0


def test_suspected_file_score_zero_recall():
    case = _case("assertion-average-off-by-one")
    record = _record_with(case.id, ["completely_wrong_file.py"])

    score = score_suspected_files(record, case)

    assert score.precision == 0.0
    assert score.recall == 0.0
    assert score.f1 is None or score.f1 == 0.0


def test_suspected_file_score_empty_suspected_files():
    case = _case("assertion-average-off-by-one")
    record = _record_with(case.id, [])

    score = score_suspected_files(record, case)

    assert score.precision == 0.0
    assert score.recall == 0.0


def test_suspected_file_score_none_when_parse_failed():
    case = _case("assertion-average-off-by-one")
    output = collect(CollectorInput(case_id=case.id))
    provider = FakeProvider(LLMResponse(raw_text="not json"))
    record = diagnose(
        case.id, output, "full_context", provider, model="m", temperature=0.0, max_tokens=10
    )

    score = score_suspected_files(record, case)

    assert score.precision is None
    assert score.recall is None
    assert score.f1 is None


def test_parse_success_rate():
    case = _case("assertion-average-off-by-one")
    ok_record = _record_with(case.id, ["stats.py"])

    output = collect(CollectorInput(case_id=case.id))
    bad_provider = FakeProvider(LLMResponse(raw_text="not json"))
    bad_record = diagnose(
        case.id, output, "full_context", bad_provider, model="m", temperature=0.0, max_tokens=10
    )

    assert parse_success_rate([ok_record, bad_record]) == 0.5
    assert parse_success_rate([]) is None


def test_insufficient_context_rate():
    case = _case("assertion-average-off-by-one")
    normal = _record_with(case.id, ["stats.py"], insufficient_context=False)
    insufficient = _record_with(case.id, [], insufficient_context=True)

    assert insufficient_context_rate([normal, insufficient]) == 0.5


def test_grounding_violation_rate():
    case = _case("assertion-average-off-by-one")
    grounded = _record_with(case.id, ["stats.py"])
    ungrounded = _record_with(case.id, ["nonexistent/unseen.py"])

    assert grounding_violation_rate([grounded, ungrounded]) == 0.5


def test_summarize_latency_and_tokens():
    case = _case("assertion-average-off-by-one")
    output = collect(CollectorInput(case_id=case.id))
    provider = FakeProvider(
        LLMResponse(
            raw_text=json.dumps(
                {
                    "root_cause_summary": "x",
                    "suspected_files": [],
                    "suspected_symbols": [],
                    "reasoning_summary": "y",
                    "diagnosis_confidence": 0.5,
                    "insufficient_context": False,
                }
            ),
            input_tokens=100,
            output_tokens=50,
            latency_seconds=2.0,
        )
    )
    record = diagnose(
        case.id, output, "full_context", provider, model="m", temperature=0.0, max_tokens=10
    )

    summary = summarize_latency_and_tokens([record])

    assert summary.count == 1
    assert summary.mean_latency_seconds == 2.0
    assert summary.mean_input_tokens == 100
    assert summary.mean_output_tokens == 50
