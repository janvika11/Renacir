import pytest

from renacir.benchmark.discovery import discover_cases
from renacir.benchmark.reconstruction import is_prepared
from renacir.benchmark.runner import apply_test_overlay, staged_case
from renacir.collector.context_selection import select_context
from renacir.collector.models import ContextSelectionLimits, ParsedFailure, TracebackFrame


def _case(case_id):
    return next(c for c in discover_cases() if c.id == case_id)


requires_prepared_real_case = pytest.mark.skipif(
    not is_prepared(_case("httpie-none-header-skip"))
    or not is_prepared(_case("httpie-custom-host-header")),
    reason="run `python -m renacir.benchmark prepare` first",
)


def test_traceback_referenced_files_are_selected():
    case = _case("assertion-average-off-by-one")
    parsed = ParsedFailure(frames=[TracebackFrame(file="test_stats.py", line=5)])

    with staged_case(case) as staged:
        selected = select_context(staged, case, parsed, ContextSelectionLimits())

    paths = {f.path for f in selected}
    assert "test_stats.py" in paths
    assert "stats.py" in paths  # local import of the failing test


def test_failing_test_rule_included_for_synthetic_case():
    case = _case("assertion-average-off-by-one")
    parsed = ParsedFailure(frames=[])  # no traceback frames at all

    with staged_case(case) as staged:
        selected = select_context(staged, case, parsed, ContextSelectionLimits())

    assert any(f.path == "test_stats.py" and f.reason == "failing_test" for f in selected)


def test_context_selection_respects_max_files():
    case = _case("import-reportpkg-broken-init")
    parsed = ParsedFailure(frames=[])
    limits = ContextSelectionLimits(max_files=1)

    with staged_case(case) as staged:
        selected = select_context(staged, case, parsed, limits)

    assert len(selected) <= 1


def test_context_selection_respects_max_lines_per_file(tmp_path_factory):
    case = _case("assertion-average-off-by-one")
    limits = ContextSelectionLimits(max_lines_per_file=1)
    parsed = ParsedFailure(frames=[TracebackFrame(file="test_stats.py", line=1)])

    with staged_case(case) as staged:
        selected = select_context(staged, case, parsed, limits)

    test_file = next(f for f in selected if f.path == "test_stats.py")
    assert test_file.truncated is True
    assert len(test_file.content.splitlines()) <= 1


def test_context_selection_respects_max_total_chars():
    case = _case("import-reportpkg-broken-init")
    limits = ContextSelectionLimits(max_total_context_chars=5, max_files=10)
    parsed = ParsedFailure(frames=[])

    with staged_case(case) as staged:
        selected = select_context(staged, case, parsed, limits)

    assert sum(len(f.content) for f in selected) <= 5


def test_context_selection_is_deterministic():
    case = _case("import-renamed-helper")
    parsed = ParsedFailure(
        frames=[TracebackFrame(file="test_main.py", line=1), TracebackFrame(file="main.py", line=1)]
    )
    limits = ContextSelectionLimits()

    with staged_case(case) as staged:
        first = select_context(staged, case, parsed, limits)
    with staged_case(case) as staged:
        second = select_context(staged, case, parsed, limits)

    assert first == second


@requires_prepared_real_case
def test_retrospective_overlay_never_selected_even_if_in_traceback():
    case = _case("httpie-none-header-skip")
    assert case.test_overlay is not None
    overlay_target = case.test_overlay.target_path

    parsed = ParsedFailure(
        frames=[
            TracebackFrame(file=overlay_target, line=17),
            TracebackFrame(file="httpie/sessions.py", line=104),
        ]
    )

    with staged_case(case) as staged:
        apply_test_overlay(case, staged)
        selected = select_context(staged, case, parsed, ContextSelectionLimits())

    paths = {f.path for f in selected}
    assert overlay_target not in paths
    assert "httpie/sessions.py" in paths


@requires_prepared_real_case
def test_failing_test_rule_and_local_import_rule_skipped_for_reconstructed_case():
    """For a real case, rules 2 (failing test file) and 3 (its local
    imports) must never run at all -- only rule 1 (traceback) can surface
    anything, and even then never the overlay itself."""
    case = _case("httpie-custom-host-header")
    parsed = ParsedFailure(frames=[])  # simulate an empty/unparseable traceback

    with staged_case(case) as staged:
        apply_test_overlay(case, staged)
        selected = select_context(staged, case, parsed, ContextSelectionLimits())

    assert selected == []
