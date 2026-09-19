"""Information-boundary tests for the Collector.

Every test here searches BOTH field names (via the pydantic model's own
field set) and the fully serialized JSON string — never just one or the
other, per the Phase 3 requirement.
"""

import pytest

from renacir.benchmark.discovery import DEFAULT_BENCHMARK_ROOT, discover_cases
from renacir.benchmark.reconstruction import is_prepared
from renacir.collector.collector import collect
from renacir.collector.models import CollectorInput, CollectorOutput

REAL_CASES = [c for c in discover_cases() if c.upstream is not None]
requires_prepared_real_cases = pytest.mark.skipif(
    not REAL_CASES or not all(is_prepared(c) for c in REAL_CASES),
    reason="run `python -m renacir.benchmark prepare` first",
)

FORBIDDEN_FIELD_NAMES = {
    "reference_repair",
    "reference",
    "independent_checks",
    "independent_check",
    "curation",
    "contamination_risk",
    "upstream",
    "test_overlay",
    "buggy_commit",
    "fix_commit",
    "fix_date",
    "dedup_cluster_id",
    "rejection_reason",
    "preparation_steps",
}

FORBIDDEN_SERIALIZED_SUBSTRINGS = (
    "fix.patch",
    "independent_check.py",
    "reference/",
    "buggy_commit",
    "fix_commit",
    "dedup_cluster_id",
    "contamination",
    "rejection_reason",
    "preparation_steps",
    "compatibility_adaptations",
)


def test_collector_output_schema_has_no_forbidden_field_names():
    assert FORBIDDEN_FIELD_NAMES.isdisjoint(set(CollectorOutput.model_fields))


@pytest.mark.parametrize(
    "case", [c for c in discover_cases() if c.upstream is None], ids=lambda c: c.id
)
def test_synthetic_case_output_has_no_forbidden_strings(case):
    output = collect(CollectorInput(case_id=case.id))
    serialized = output.model_dump_json().lower()

    for forbidden in FORBIDDEN_SERIALIZED_SUBSTRINGS:
        assert forbidden.lower() not in serialized, (
            f"{case.id}: found forbidden string {forbidden!r}"
        )


@pytest.mark.parametrize(
    "case", [c for c in discover_cases() if c.upstream is None], ids=lambda c: c.id
)
def test_reference_repair_patch_content_never_appears(case):
    patch_path = DEFAULT_BENCHMARK_ROOT / case.path / case.reference_repair.patch
    patch_text = patch_path.read_text()
    # The added/removed lines are the solution-revealing part -- check each
    # non-trivial line individually rather than the whole diff as one blob,
    # since diff headers alone (e.g. "+++") would trivially never match.
    meaningful_lines = [
        line
        for line in patch_text.splitlines()
        if line.startswith(("+", "-")) and len(line.strip()) > 3
    ]

    output = collect(CollectorInput(case_id=case.id))
    serialized = output.model_dump_json()

    for line in meaningful_lines:
        assert line not in serialized, f"{case.id}: reference-repair line leaked: {line!r}"


@pytest.mark.parametrize(
    "case",
    [c for c in discover_cases() if c.upstream is None and c.independent_checks],
    ids=lambda c: c.id,
)
def test_independent_check_content_never_appears(case):
    output = collect(CollectorInput(case_id=case.id))
    serialized = output.model_dump_json()

    failing_test_file = case.failing_test.split("::", 1)[0]
    failing_test_lines = set(
        (DEFAULT_BENCHMARK_ROOT / case.path / failing_test_file).read_text().splitlines()
    )

    for check in case.independent_checks:
        check_path = DEFAULT_BENCHMARK_ROOT / case.path / check.path
        check_text = check_path.read_text()
        # Exclude lines that legitimately also appear in the (allowed)
        # failing test file itself -- e.g. both files may share an identical
        # `from module import symbol` import line without that being a
        # leak of the independent check specifically. Only lines distinctive
        # to the independent check are checked.
        distinctive_lines = [
            line
            for line in check_text.splitlines()
            if line.strip() and not line.startswith("#") and line not in failing_test_lines
        ]
        for line in distinctive_lines:
            assert line not in serialized, f"{case.id}: independent-check line leaked: {line!r}"
        assert check.path not in serialized
        assert check.description not in serialized


@requires_prepared_real_cases
@pytest.mark.parametrize("case", REAL_CASES, ids=lambda c: c.id)
def test_real_case_output_has_no_forbidden_strings(case):
    output = collect(CollectorInput(case_id=case.id))
    serialized = output.model_dump_json().lower()

    for forbidden in FORBIDDEN_SERIALIZED_SUBSTRINGS:
        assert forbidden.lower() not in serialized, (
            f"{case.id}: found forbidden string {forbidden!r}"
        )

    assert case.upstream.buggy_commit not in serialized
    assert case.upstream.fix_commit not in serialized
    assert case.upstream.repository_url not in serialized


@requires_prepared_real_cases
@pytest.mark.parametrize("case", REAL_CASES, ids=lambda c: c.id)
def test_real_case_reference_repair_content_never_appears(case):
    patch_path = DEFAULT_BENCHMARK_ROOT / case.path / case.reference_repair.patch
    patch_text = patch_path.read_text()
    meaningful_lines = [
        line
        for line in patch_text.splitlines()
        if line.startswith(("+", "-")) and len(line.strip()) > 3
    ]

    output = collect(CollectorInput(case_id=case.id))
    serialized = output.model_dump_json()

    for line in meaningful_lines:
        assert line not in serialized, f"{case.id}: reference-repair line leaked: {line!r}"


@requires_prepared_real_cases
@pytest.mark.parametrize("case", REAL_CASES, ids=lambda c: c.id)
def test_real_case_independent_check_content_never_appears(case):
    output = collect(CollectorInput(case_id=case.id))
    serialized = output.model_dump_json()

    for check in case.independent_checks:
        check_path = DEFAULT_BENCHMARK_ROOT / case.path / check.path
        check_text = check_path.read_text()
        meaningful_lines = [
            line for line in check_text.splitlines() if line.strip() and not line.startswith("#")
        ]
        for line in meaningful_lines:
            assert line not in serialized, f"{case.id}: independent-check line leaked: {line!r}"


@requires_prepared_real_cases
@pytest.mark.parametrize("case", REAL_CASES, ids=lambda c: c.id)
def test_retrospective_overlay_source_never_appears(case):
    """The strongest leakage test in this suite: the literal source text of
    the retrospective test overlay -- which Collector MUST execute to
    observe the failure at all -- must never appear anywhere in the
    serialized output, field names or values."""
    assert case.test_overlay is not None

    overlay_path = DEFAULT_BENCHMARK_ROOT / case.path / case.test_overlay.path
    overlay_text = overlay_path.read_text()
    meaningful_lines = [
        line
        for line in overlay_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    output = collect(CollectorInput(case_id=case.id))
    serialized = output.model_dump_json()

    assert output.failing_test_provenance == "reconstructed_retrospective_overlay"
    assert not any(f.path == case.test_overlay.target_path for f in output.selected_context)
    for line in meaningful_lines:
        assert line not in serialized, f"{case.id}: retrospective overlay line leaked: {line!r}"
