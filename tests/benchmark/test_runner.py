import pytest

from renacir.benchmark.discovery import discover_cases
from renacir.benchmark.runner import evaluate_case


@pytest.mark.parametrize("case", discover_cases(), ids=lambda case: case.id)
def test_case_fails_before_patch_and_passes_after(case):
    result = evaluate_case(case)

    assert result.pre_patch_passed is False, f"{case.id} should fail before the ground-truth patch"
    assert result.post_patch_passed is True, f"{case.id} should pass after the ground-truth patch"
