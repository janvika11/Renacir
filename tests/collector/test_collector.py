import hashlib

import pytest

from renacir.benchmark.discovery import DEFAULT_BENCHMARK_ROOT, discover_cases
from renacir.benchmark.reconstruction import is_prepared
from renacir.collector.collector import UnknownCaseError, collect
from renacir.collector.models import CollectorInput

REAL_CASES = [c for c in discover_cases() if c.upstream is not None]
requires_prepared_real_cases = pytest.mark.skipif(
    not REAL_CASES or not all(is_prepared(c) for c in REAL_CASES),
    reason="run `python -m renacir.benchmark prepare` first",
)


def _checksum(path):
    h = hashlib.sha256()
    for f in sorted(path.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts and ".pytest_cache" not in f.parts:
            h.update(str(f.relative_to(path)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def test_collect_captures_real_execution_not_a_fake():
    output = collect(CollectorInput(case_id="assertion-average-off-by-one"))

    assert output.exit_code != 0
    assert "average" in output.stdout
    assert output.parsed_failure.error_type == "AssertionError"


def test_collect_unknown_case_raises():
    with pytest.raises(UnknownCaseError):
        collect(CollectorInput(case_id="does-not-exist"))


@pytest.mark.parametrize(
    "case", [c for c in discover_cases() if c.upstream is None], ids=lambda c: c.id
)
def test_collect_never_mutates_the_original_fixture(case):
    case_dir = DEFAULT_BENCHMARK_ROOT / case.path
    before = _checksum(case_dir)

    collect(CollectorInput(case_id=case.id))

    after = _checksum(case_dir)
    assert before == after


def test_collect_is_deterministic_across_repeated_runs():
    first = collect(CollectorInput(case_id="assertion-average-off-by-one"))
    second = collect(CollectorInput(case_id="assertion-average-off-by-one"))

    assert first == second


def test_collect_is_deterministic_for_import_case():
    first = collect(CollectorInput(case_id="import-renamed-helper"))
    second = collect(CollectorInput(case_id="import-renamed-helper"))

    assert first == second


def test_collect_respects_configured_limits():
    from renacir.collector.models import ContextSelectionLimits

    output = collect(
        CollectorInput(
            case_id="assertion-average-off-by-one",
            limits=ContextSelectionLimits(max_files=1, max_stdout_chars=5),
        )
    )

    assert len(output.selected_context) <= 1
    assert len(output.stdout) <= 5
    assert output.limits_applied.max_files == 1


@requires_prepared_real_cases
@pytest.mark.parametrize("case", REAL_CASES, ids=lambda c: c.id)
def test_collect_against_reconstructed_real_case(case):
    output = collect(CollectorInput(case_id=case.id))

    assert output.exit_code != 0
    assert output.failing_test_provenance == "reconstructed_retrospective_overlay"


@requires_prepared_real_cases
def test_collect_is_deterministic_for_a_real_case():
    case = REAL_CASES[0]
    first = collect(CollectorInput(case_id=case.id))
    second = collect(CollectorInput(case_id=case.id))

    assert first == second


@requires_prepared_real_cases
def test_collect_never_mutates_the_reconstruction_cache():
    from renacir.benchmark.reconstruction import repo_dir

    case = REAL_CASES[0]
    cache_repo = repo_dir(case)
    before = _checksum(cache_repo)

    collect(CollectorInput(case_id=case.id))

    after = _checksum(cache_repo)
    assert before == after
