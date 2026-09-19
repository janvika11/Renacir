import pytest
from pydantic import ValidationError

from renacir.collector.models import (
    CollectorInput,
    CollectorOutput,
    ContextSelectionLimits,
    ParsedFailure,
    RuntimeInfo,
)


def test_collector_input_has_conservative_default_limits():
    collector_input = CollectorInput(case_id="assertion-average-off-by-one")

    assert collector_input.limits.max_files > 0
    assert collector_input.limits.max_total_context_chars > 0


def test_context_selection_limits_are_configurable():
    limits = ContextSelectionLimits(max_files=1, max_lines_per_file=10)

    assert limits.max_files == 1
    assert limits.max_lines_per_file == 10
    # unspecified fields keep their documented conservative defaults
    assert limits.max_total_context_chars == 60_000


def test_collector_output_requires_all_core_fields():
    with pytest.raises(ValidationError):
        CollectorOutput(case_id="x")


def test_collector_output_round_trips_through_json():
    output = CollectorOutput(
        case_id="assertion-average-off-by-one",
        context={
            "failing_test": "test_stats.py::test_average_of_three",
            "command": ["pytest", "-q"],
            "category": "assertion",
        },
        failing_test_provenance="original_fixture",
        exit_code=1,
        stdout="F",
        stderr="",
        parsed_failure=ParsedFailure(),
        selected_context=[],
        repository_structure=["test_stats.py", "stats.py"],
        runtime=RuntimeInfo(python_version="3.11.9"),
        limits_applied=ContextSelectionLimits(),
    )

    restored = CollectorOutput.model_validate_json(output.model_dump_json())
    assert restored == output


def test_failing_test_provenance_is_restricted_to_two_values():
    with pytest.raises(ValidationError):
        CollectorOutput(
            case_id="x",
            context={"failing_test": "t.py::t", "command": ["pytest"], "category": "assertion"},
            failing_test_provenance="something_else",
            exit_code=0,
            stdout="",
            stderr="",
            parsed_failure=ParsedFailure(),
            selected_context=[],
            repository_structure=[],
            runtime=RuntimeInfo(python_version="3.11.9"),
            limits_applied=ContextSelectionLimits(),
        )
