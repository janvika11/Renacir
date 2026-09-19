"""Evaluator-only retrieval-completeness diagnostic.

Deliberately lives OUTSIDE `renacir.collector` — Collector must never depend
on reference-repair knowledge, and this module exists specifically to
measure Collector's context-selection policy against known benchmark
answers, never to inform it. Nothing in `renacir.collector` imports from
this module; nothing here is reachable from `collect()`.

`RetrievalDiagnostic` is NOT part of `ModelFacingContext` and NOT part of
`CollectorOutput` — it is computed as a separate step, strictly AFTER
`collect()` has already returned, from a `CollectorOutput` plus (evaluator-
only) knowledge of the benchmark case's reference repair. Changing what the
reference repair touches cannot change `selected_context`, `stdout`,
`stderr`, `parsed_failure`, or `context` — see
`tests/evaluation/test_retrieval.py::test_reference_relevance_cannot_influence_collection`.

**What this diagnostic is not** (see `docs/collector.md` for the full
statement): it is not a claim that reference-repair-touched files are the
only relevant files for diagnosis, that file recall measures semantic
context quality, or that higher recall guarantees successful diagnosis. It
is a transparent, narrow proxy — "did context selection retrieve the files
the historical fix actually touched" — nothing more.
"""

from pydantic import BaseModel

from renacir.benchmark.discovery import DEFAULT_BENCHMARK_ROOT
from renacir.benchmark.models import BenchmarkCase
from renacir.collector.models import CollectorOutput


class RetrievalDiagnostic(BaseModel):
    """Evaluator-only. See module docstring for what this is and is not."""

    selected_file_count: int
    selected_total_chars: int
    selected_total_lines: int
    selection_reasons: dict[str, int]
    empty_context: bool
    truncation_occurred: bool

    # `None` (not `False`) when no meaningful reference-file set could be
    # derived for this case — never fabricated. `False` would wrongly imply
    # "checked, and no reference files exist."
    reference_relevant_files_available: bool | None
    reference_relevant_files_retrieved: int | None
    reference_relevant_files_total: int | None
    reference_relevant_file_recall: float | None


def reference_relevant_files(
    case: BenchmarkCase, benchmark_root=DEFAULT_BENCHMARK_ROOT
) -> list[str] | None:
    """Evaluator-only. The production file(s) the case's reference repair
    actually modifies — NOT "files relevant for diagnosis" in any broader
    sense, and NOT derived from where a bug's root cause conceptually
    lives. For `import-renamed-helper`, for example, this is `main.py`
    (where the fix's import statement changed), not `helpers.py` (which
    defines the renamed symbol but is never itself modified by the fix) —
    a real, checked distinction, not a hypothetical one; see
    `docs/collector.md`.

    For a real case, reads the already-recorded, verified
    `upstream.production_files` directly (no re-parsing). For a synthetic
    case, parses `+++ b/<path>` headers out of the stored `fix.patch`.
    Returns `None` — never an invented/empty-but-confident answer — when no
    file list can be derived at all (e.g. the patch is missing or has no
    recognizable diff header).
    """
    if case.upstream is not None:
        files = list(case.upstream.production_files)
        return files or None

    patch_path = benchmark_root / case.path / case.reference_repair.patch
    if not patch_path.is_file():
        return None

    files = [
        line[len("+++ b/") :]
        for line in patch_path.read_text().splitlines()
        if line.startswith("+++ b/")
    ]
    return files or None


def compute_retrieval_diagnostic(
    output: CollectorOutput,
    case: BenchmarkCase,
    benchmark_root=DEFAULT_BENCHMARK_ROOT,
) -> RetrievalDiagnostic:
    """Compute a `RetrievalDiagnostic` for an already-produced
    `CollectorOutput`. Read-only with respect to `output` — never mutates
    or re-runs collection, never touches `case.reference_repair`/`.upstream`
    for anything other than this diagnostic's own bookkeeping.
    """
    selection_reasons: dict[str, int] = {}
    total_chars = 0
    total_lines = 0
    for f in output.selected_context:
        selection_reasons[f.reason] = selection_reasons.get(f.reason, 0) + 1
        total_chars += len(f.content)
        total_lines += len(f.content.splitlines())

    reference_files = reference_relevant_files(case, benchmark_root)
    if reference_files is None:
        available: bool | None = False
        retrieved: int | None = None
        total: int | None = None
        recall: float | None = None
    else:
        available = True
        selected_paths = {f.path for f in output.selected_context}
        total = len(reference_files)
        retrieved = sum(1 for rf in reference_files if rf in selected_paths)
        recall = retrieved / total if total else None

    return RetrievalDiagnostic(
        selected_file_count=len(output.selected_context),
        selected_total_chars=total_chars,
        selected_total_lines=total_lines,
        selection_reasons=selection_reasons,
        empty_context=len(output.selected_context) == 0,
        truncation_occurred=any(f.truncated for f in output.selected_context),
        reference_relevant_files_available=available,
        reference_relevant_files_retrieved=retrieved,
        reference_relevant_files_total=total,
        reference_relevant_file_recall=recall,
    )
