"""Tests for the evaluator-only retrieval-completeness diagnostic.

These measure Collector's existing, unchanged context-selection policy —
they do not exercise or require any change to `renacir.collector`.
"""

import pytest

from renacir.benchmark.discovery import discover_cases
from renacir.benchmark.reconstruction import is_prepared
from renacir.collector.collector import collect
from renacir.collector.models import CollectorInput, ContextSelectionLimits
from renacir.evaluation.retrieval import compute_retrieval_diagnostic, reference_relevant_files


def _case(case_id):
    return next(c for c in discover_cases() if c.id == case_id)


def test_synthetic_case_reference_file_is_retrieved():
    """assertion-average-off-by-one: the reference repair touches stats.py,
    which context selection already retrieves via the local-import rule."""
    case = _case("assertion-average-off-by-one")
    output = collect(CollectorInput(case_id=case.id))
    diagnostic = compute_retrieval_diagnostic(output, case)

    assert diagnostic.reference_relevant_files_available is True
    assert diagnostic.reference_relevant_files_total == 1
    assert diagnostic.reference_relevant_files_retrieved == 1
    assert diagnostic.reference_relevant_file_recall == 1.0
    assert diagnostic.empty_context is False


def test_import_renamed_helper_reference_file_is_actually_main_py_not_helpers_py():
    """Correction to an earlier, imprecise claim in docs/collector.md: the
    historical fix for this case modifies main.py's import statement, NOT
    helpers.py (which defines the renamed symbol but is never itself
    touched by the repair) -- confirmed directly against the stored patch.
    'Where the root cause conceptually lives' and 'what the repair touches'
    are different questions; this diagnostic answers only the second one.

    Because main.py is already selected via the traceback rule (rule 1),
    this case shows COMPLETE recall under the repair-touched-files
    definition -- not the incomplete recall a looser, root-cause-based
    notion of relevance might suggest. This is reported as measured, not
    adjusted to fit a prior expectation.
    """
    case = _case("import-renamed-helper")
    assert reference_relevant_files(case) == ["main.py"]

    output = collect(CollectorInput(case_id=case.id))
    diagnostic = compute_retrieval_diagnostic(output, case)

    assert diagnostic.reference_relevant_files_total == 1
    assert diagnostic.reference_relevant_files_retrieved == 1
    assert diagnostic.reference_relevant_file_recall == 1.0
    # helpers.py -- the file single-hop traversal cannot reach -- is real,
    # but it is not part of the *repair-touched* reference set at all.
    assert "helpers.py" not in reference_relevant_files(case)
    assert not any(f.path == "helpers.py" for f in output.selected_context)


@pytest.mark.skipif(
    not is_prepared(_case("httpie-custom-host-header")),
    reason="run `python -m renacir.benchmark prepare` first",
)
def test_httpie_custom_host_header_shows_zero_recall_kept_as_measured():
    """This case's only traceback frame is the withheld retrospective test
    overlay, so selected_context is empty and recall is genuinely 0 --
    kept as-is, not adjusted, per the Phase 3 audit instruction."""
    case = _case("httpie-custom-host-header")
    output = collect(CollectorInput(case_id=case.id))
    diagnostic = compute_retrieval_diagnostic(output, case)

    assert diagnostic.empty_context is True
    assert diagnostic.reference_relevant_files_available is True
    assert diagnostic.reference_relevant_files_total == 1
    assert diagnostic.reference_relevant_files_retrieved == 0
    assert diagnostic.reference_relevant_file_recall == 0.0


def test_no_applicable_reference_relevance_yields_none_not_invented(tmp_path):
    """No real benchmark case currently lacks a parseable reference-file
    set (every patch has a `+++ b/<path>` header, every real case has
    `upstream.production_files`) -- this constructs the missing-patch
    condition directly to prove `None` propagates rather than a fabricated
    0/0 or False being reported as if it were a checked answer."""
    case = _case("assertion-average-off-by-one")
    empty_benchmark_root = tmp_path  # no `cases/.../reference/fix.patch` here

    assert reference_relevant_files(case, benchmark_root=empty_benchmark_root) is None

    output = collect(CollectorInput(case_id=case.id))
    diagnostic = compute_retrieval_diagnostic(output, case, benchmark_root=empty_benchmark_root)

    assert diagnostic.reference_relevant_files_available is False
    assert diagnostic.reference_relevant_files_retrieved is None
    assert diagnostic.reference_relevant_files_total is None
    assert diagnostic.reference_relevant_file_recall is None


def test_truncation_is_accounted_for():
    case = _case("assertion-average-off-by-one")
    output = collect(
        CollectorInput(case_id=case.id, limits=ContextSelectionLimits(max_lines_per_file=1))
    )
    diagnostic = compute_retrieval_diagnostic(output, case)

    assert any(f.truncated for f in output.selected_context)
    assert diagnostic.truncation_occurred is True


def test_selection_reasons_are_counted():
    case = _case("assertion-average-off-by-one")
    output = collect(CollectorInput(case_id=case.id))
    diagnostic = compute_retrieval_diagnostic(output, case)

    assert diagnostic.selected_file_count == len(output.selected_context)
    assert sum(diagnostic.selection_reasons.values()) == diagnostic.selected_file_count


def test_reference_relevance_cannot_influence_collection(tmp_path):
    """The critical leakage-independence property: changing the reference
    repair's touched-file metadata cannot change `selected_context`,
    `stdout`, `stderr`, `parsed_failure`, or `context` for the same buggy
    execution -- because the diagnostic is computed strictly AFTER
    `collect()` returns, and never feeds anything back into it.

    Proven two ways: (1) `collect()` is called exactly once; the SAME
    `CollectorOutput` object is scored against two maximally different
    reference-file answers (the case's real reference set vs. `None`, via a
    benchmark_root with no patch file) and is provably untouched by either
    call, since Python object identity/equality holds before and after.
    (2) `collect()` is called a second, independent time and produces a
    bit-for-bit identical `CollectorOutput`, confirming evaluator-side
    scoring in between had no observable effect on collection itself.
    """
    case = _case("assertion-average-off-by-one")
    output = collect(CollectorInput(case_id=case.id))
    output_before = output.model_copy(deep=True)

    real_diagnostic = compute_retrieval_diagnostic(output, case)
    fabricated_diagnostic = compute_retrieval_diagnostic(output, case, benchmark_root=tmp_path)

    # The two diagnostics genuinely differ (proving the reference-file
    # answer actually changed between calls)...
    assert real_diagnostic.reference_relevant_files_available is True
    assert fabricated_diagnostic.reference_relevant_files_available is False

    # ...yet `output` itself -- the only thing Diagnoser would ever see --
    # is untouched by either call.
    assert output == output_before

    # And a fully independent second collection run is unaffected too.
    output_again = collect(CollectorInput(case_id=case.id))
    assert output_again == output_before
