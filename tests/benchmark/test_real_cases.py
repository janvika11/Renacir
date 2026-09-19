"""Real (REAL-CI-C) case reproduction tests.

Each of these requires `prepare_case` to have already run for that case
(network access, one-time, cached under `.benchmark-cache/`) — see
`renacir.benchmark.reconstruction`. A test is skipped, not failed, when its
case hasn't been prepared, so a fresh clone's `pytest -q` run stays offline
and green; run `python -m renacir.benchmark prepare` first to exercise
these.
"""

import pytest

from renacir.benchmark.discovery import discover_cases
from renacir.benchmark.reconstruction import is_prepared
from renacir.benchmark.runner import evaluate_case

REAL_CASES = [c for c in discover_cases() if c.upstream is not None]


def _prepared_real_cases():
    return [pytest.param(c, id=c.id) for c in REAL_CASES if is_prepared(c)]


@pytest.mark.parametrize("case", REAL_CASES, ids=lambda case: case.id)
def test_real_case_has_real_ci_c_subtype(case):
    assert case.upstream.real_ci_subtype == "real_ci_c"


@pytest.mark.parametrize("case", REAL_CASES, ids=lambda case: case.id)
def test_real_case_has_pinned_commits_and_license(case):
    assert case.upstream.buggy_commit
    assert case.upstream.fix_commit
    assert case.upstream.buggy_commit != case.upstream.fix_commit
    assert case.upstream.license
    assert case.upstream.license_verification_note


def test_httpie_cases_share_a_source_group():
    cases = {c.id: c for c in REAL_CASES}
    groups = {
        cases["httpie-none-header-skip"].source.source_group_id,
        cases["httpie-custom-host-header"].source.source_group_id,
    }
    assert groups == {"real:httpie-cli"}


def test_click_case_has_its_own_source_group():
    cases = {c.id: c for c in REAL_CASES}
    click_group = cases["click-path-resolve-symlink"].source.source_group_id
    httpie_group = cases["httpie-none-header-skip"].source.source_group_id
    assert click_group != httpie_group


@pytest.mark.skipif(
    not REAL_CASES or not all(is_prepared(c) for c in REAL_CASES),
    reason="run `python -m renacir.benchmark prepare` first",
)
@pytest.mark.parametrize("case", REAL_CASES, ids=lambda case: case.id)
def test_real_case_fails_before_patch_and_passes_after(case):
    result = evaluate_case(case)

    assert result.pre_patch_passed is False, f"{case.id} should fail before the reference repair"
    assert result.post_patch_passed is True, f"{case.id} should pass after the reference repair"


@pytest.mark.skipif(
    not REAL_CASES or not all(is_prepared(c) for c in REAL_CASES),
    reason="run `python -m renacir.benchmark prepare` first",
)
@pytest.mark.parametrize("case", REAL_CASES, ids=lambda case: case.id)
def test_real_case_independent_checks_pass_after_reference_repair(case):
    result = evaluate_case(case)

    assert result.independent_checks_passed is True, (
        f"{case.id}: independent correctness check(s) failed against the repaired code"
    )
