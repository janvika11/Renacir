import pytest

from renacir.benchmark.discovery import discover_cases
from renacir.benchmark.runner import evaluate_case


@pytest.mark.parametrize("case", discover_cases(), ids=lambda case: case.id)
def test_case_fails_before_patch_and_passes_after(case):
    result = evaluate_case(case)

    assert result.pre_patch_passed is False, f"{case.id} should fail before the reference repair"
    assert result.post_patch_passed is True, f"{case.id} should pass after the reference repair"


@pytest.mark.parametrize(
    "case",
    [c for c in discover_cases() if c.independent_checks],
    ids=lambda case: case.id,
)
def test_independent_checks_pass_after_reference_repair(case):
    result = evaluate_case(case)

    assert len(result.independent_check_results) == len(case.independent_checks)
    assert result.independent_checks_passed is True, (
        f"{case.id}: independent correctness check(s) failed against the repaired code"
    )


@pytest.mark.parametrize(
    "case",
    [c for c in discover_cases() if not c.independent_checks],
    ids=lambda case: case.id,
)
def test_cases_without_independent_checks_report_vacuously_passed(case):
    result = evaluate_case(case)

    assert result.independent_check_results == []
    assert result.independent_checks_passed is True
