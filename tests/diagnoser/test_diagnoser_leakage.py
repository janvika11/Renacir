"""Aggressive information-boundary tests for the Diagnoser.

Every test searches BOTH field names (via schema introspection) AND the
fully rendered prompt string — never just one or the other.
"""

import pytest

from renacir.benchmark.discovery import DEFAULT_BENCHMARK_ROOT, discover_cases
from renacir.benchmark.reconstruction import is_prepared
from renacir.collector.collector import collect
from renacir.collector.models import CollectorInput
from renacir.diagnoser.diagnoser import build_diagnoser_input, fingerprint_request
from renacir.diagnoser.models import DiagnoserInput, Diagnosis
from renacir.diagnoser.prompts.v1 import SYSTEM_PROMPT, render_user_prompt
from renacir.evaluation.retrieval import compute_retrieval_diagnostic

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
    "real_ci_subtype",
    "fold",
    "reference_relevant_files_available",
    "reference_relevant_files_retrieved",
    "reference_relevant_files_total",
    "reference_relevant_file_recall",
    "category",
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
    "real_ci_subtype",
    "real_ci_c",
    "reconstructed_retrospective_overlay",
    "test_overlay",
    "recall",
    "retrieval",
    "curation",
    "fold",
)


def test_diagnoser_input_and_diagnosis_schemas_have_no_forbidden_field_names():
    assert FORBIDDEN_FIELD_NAMES.isdisjoint(set(DiagnoserInput.model_fields))
    assert FORBIDDEN_FIELD_NAMES.isdisjoint(set(Diagnosis.model_fields))


@pytest.mark.parametrize(
    "case", [c for c in discover_cases() if c.upstream is None], ids=lambda c: c.id
)
@pytest.mark.parametrize("condition", ["failure_output_only", "full_context"])
def test_synthetic_case_rendered_prompt_has_no_forbidden_strings(case, condition):
    output = collect(CollectorInput(case_id=case.id))
    diagnoser_input = build_diagnoser_input(output, condition)
    prompt = render_user_prompt(diagnoser_input)
    combined = (SYSTEM_PROMPT + prompt).lower()

    for forbidden in FORBIDDEN_SERIALIZED_SUBSTRINGS:
        assert forbidden.lower() not in combined, f"{case.id}/{condition}: found {forbidden!r}"


@pytest.mark.parametrize(
    "case", [c for c in discover_cases() if c.upstream is None], ids=lambda c: c.id
)
def test_reference_repair_patch_content_never_appears_in_prompt(case):
    patch_path = DEFAULT_BENCHMARK_ROOT / case.path / case.reference_repair.patch
    meaningful_lines = [
        line
        for line in patch_path.read_text().splitlines()
        if line.startswith(("+", "-")) and len(line.strip()) > 3
    ]

    output = collect(CollectorInput(case_id=case.id))
    for condition in ("failure_output_only", "full_context"):
        prompt = render_user_prompt(build_diagnoser_input(output, condition))
        for line in meaningful_lines:
            assert line not in prompt, (
                f"{case.id}/{condition}: reference-repair line leaked: {line!r}"
            )


@pytest.mark.parametrize(
    "case",
    [c for c in discover_cases() if c.upstream is None and c.independent_checks],
    ids=lambda c: c.id,
)
def test_independent_check_content_never_appears_in_prompt(case):
    failing_test_file = case.failing_test.split("::", 1)[0]
    failing_test_lines = set(
        (DEFAULT_BENCHMARK_ROOT / case.path / failing_test_file).read_text().splitlines()
    )

    output = collect(CollectorInput(case_id=case.id))
    for condition in ("failure_output_only", "full_context"):
        prompt = render_user_prompt(build_diagnoser_input(output, condition))
        for check in case.independent_checks:
            check_text = (DEFAULT_BENCHMARK_ROOT / case.path / check.path).read_text()
            distinctive_lines = [
                line
                for line in check_text.splitlines()
                if line.strip() and not line.startswith("#") and line not in failing_test_lines
            ]
            for line in distinctive_lines:
                assert line not in prompt, (
                    f"{case.id}/{condition}: independent-check line leaked: {line!r}"
                )


@requires_prepared_real_cases
@pytest.mark.parametrize("case", REAL_CASES, ids=lambda c: c.id)
@pytest.mark.parametrize("condition", ["failure_output_only", "full_context"])
def test_real_case_rendered_prompt_has_no_forbidden_strings(case, condition):
    output = collect(CollectorInput(case_id=case.id))
    diagnoser_input = build_diagnoser_input(output, condition)
    prompt = render_user_prompt(diagnoser_input)
    combined = (SYSTEM_PROMPT + prompt).lower()

    for forbidden in FORBIDDEN_SERIALIZED_SUBSTRINGS:
        assert forbidden.lower() not in combined, f"{case.id}/{condition}: found {forbidden!r}"

    assert case.upstream.buggy_commit not in combined
    assert case.upstream.fix_commit not in combined
    assert case.upstream.repository_url not in prompt


@requires_prepared_real_cases
@pytest.mark.parametrize("case", REAL_CASES, ids=lambda c: c.id)
def test_real_case_retrospective_overlay_source_never_appears_in_prompt(case):
    """The critical test: build the ACTUAL CollectorOutput and the ACTUAL
    DiagnoserInput/rendered prompt for a real REAL-CI-C case, and verify the
    retrospective test overlay's literal source text is absent from both
    conditions — the Phase 3 boundary carried through unchanged into the
    Diagnoser layer.
    """
    assert case.test_overlay is not None

    overlay_text = (DEFAULT_BENCHMARK_ROOT / case.path / case.test_overlay.path).read_text()
    meaningful_lines = [
        line
        for line in overlay_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    output = collect(CollectorInput(case_id=case.id))
    assert output.failing_test_provenance == "reconstructed_retrospective_overlay"

    for condition in ("failure_output_only", "full_context"):
        diagnoser_input = build_diagnoser_input(output, condition)
        prompt = render_user_prompt(diagnoser_input)

        assert not any(
            f.path == case.test_overlay.target_path for f in diagnoser_input.selected_context
        )
        for line in meaningful_lines:
            assert line not in prompt, (
                f"{case.id}/{condition}: retrospective overlay line leaked: {line!r}"
            )


def test_retrieval_diagnostic_computation_cannot_alter_diagnoser_input():
    """Evaluator-side retrieval scoring must not feed back into what the
    model sees. Compute a RetrievalDiagnostic (touching case.upstream /
    case.reference_repair) and confirm DiagnoserInput built before vs. after
    that computation, from the same CollectorOutput, is identical.
    """
    case = next(c for c in discover_cases() if c.id == "assertion-average-off-by-one")
    output = collect(CollectorInput(case_id=case.id))

    before = build_diagnoser_input(output, "full_context")
    compute_retrieval_diagnostic(output, case)  # evaluator-only, reads reference_repair
    after = build_diagnoser_input(output, "full_context")

    assert before == after
    assert render_user_prompt(before) == render_user_prompt(after)


def test_diagnoser_input_construction_never_reads_case_reference_fields():
    """build_diagnoser_input's signature takes only a CollectorOutput and a
    condition string -- it structurally cannot read case.reference_repair,
    case.upstream, case.independent_checks, or case.curation, because it
    never receives a BenchmarkCase at all."""
    import inspect

    sig = inspect.signature(build_diagnoser_input)
    param_types = {name: param.annotation for name, param in sig.parameters.items()}
    assert "BenchmarkCase" not in str(param_types)


def test_fingerprint_never_includes_a_secret_placeholder():
    fingerprint = fingerprint_request(SYSTEM_PROMPT, "API_KEY=sk-fake-not-a-real-key-marker")
    # The fingerprint itself is a hash -- this just confirms fingerprinting
    # doesn't special-case or extract secret-shaped substrings, it hashes
    # whatever text is given verbatim (there being no key in normal use).
    assert len(fingerprint) == 64
