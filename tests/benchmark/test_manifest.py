import pytest

from renacir.benchmark.discovery import DEFAULT_BENCHMARK_ROOT, discover_cases, validate_case_paths


def test_discover_cases_returns_both_seed_cases():
    cases = discover_cases()
    ids = {case.id for case in cases}

    assert ids == {"assertion-average-off-by-one", "import-renamed-helper"}


def test_case_ids_are_unique():
    cases = discover_cases()
    ids = [case.id for case in cases]

    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("case", discover_cases(), ids=lambda case: case.id)
def test_case_category_is_known(case):
    assert case.category in {"assertion", "import"}


@pytest.mark.parametrize("case", discover_cases(), ids=lambda case: case.id)
def test_case_referenced_paths_exist_on_disk(case):
    validate_case_paths(case, DEFAULT_BENCHMARK_ROOT)
