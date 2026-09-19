"""Collector input/output schema.

The Collector executes a benchmark/reconstructed failure and packages
deterministic, bounded, model-facing evidence for a future Diagnoser — see
`docs/collector.md` for the full contract, context-selection rules, and
information-boundary guarantees this module and `renacir.collector.collector`
implement together.

`CollectorOutput.context` reuses `renacir.benchmark.context.ModelFacingContext`
(the existing Tier-B allowlist) rather than re-deriving `failing_test`/
`command`/`category` — one allowlist, not a second, conflicting definition.

Scope note: this phase's Collector consumes benchmark cases (synthetic
fixtures and reconstructed real-world REAL-CI-C cases) via the existing
`renacir.benchmark` staging/execution infrastructure. It does not ingest a
live GitHub Actions run — that is a later integration phase, not built here
(see `ARCHITECTURE.md`'s Collector description and `docs/collector.md`).
"""

from typing import Literal

from pydantic import BaseModel

from renacir.benchmark.context import ModelFacingContext

FailingTestProvenance = Literal["original_fixture", "reconstructed_retrospective_overlay"]
SelectedFileReason = Literal["failing_test", "traceback_reference", "local_import"]


class ContextSelectionLimits(BaseModel):
    """Explicit, conservative, stated ceilings — a bounding choice, not
    derived from data (the same methodological status as the repository-size
    field in `docs/research_protocol.md` §5: descriptive/bounding, not a
    claim these exact numbers are correct). Configurable; every
    `CollectorOutput.limits_applied` records what was actually used, so a
    given run's context selection is always reproducible/inspectable.
    """

    max_files: int = 5
    max_lines_per_file: int = 200
    max_chars_per_file: int = 20_000
    max_total_context_chars: int = 60_000
    max_stdout_chars: int = 10_000
    max_stderr_chars: int = 10_000


class CollectorInput(BaseModel):
    case_id: str
    limits: ContextSelectionLimits = ContextSelectionLimits()


class TracebackFrame(BaseModel):
    """One frame of a parsed pytest failure report. `file` is always
    relative to the case root — never an absolute host path, and never a
    path inside `venv/`, `site-packages/`, or `.benchmark-cache/` (filtered
    out in `renacir.collector.parsing`), so a real case's local reconstruction
    cache directory structure is never exposed.
    """

    file: str
    line: int | None = None
    function: str | None = None


class ParsedFailure(BaseModel):
    """Deterministically parsed from stdout — never guessed. Fields are
    `None`/empty when parsing can't determine them with confidence; raw
    `stdout`/`stderr` on `CollectorOutput` always preserve the full
    underlying evidence regardless of what this managed to parse out.
    """

    error_type: str | None = None
    error_message: str | None = None
    frames: list[TracebackFrame] = []
    summary: str | None = None


class SelectedFile(BaseModel):
    """One file chosen by `renacir.collector.context_selection.select_context`.
    Never present for a path equal to a real case's `test_overlay.target_path`
    — see that module's docstring for why.
    """

    path: str
    content: str
    truncated: bool
    reason: SelectedFileReason


class RuntimeInfo(BaseModel):
    """What was genuinely observed of the runtime that actually executed the
    failing test this run — never `upstream.historical_runtime` (Tier C,
    evaluator-only reasoning about an assumed original environment) and never
    `upstream.reconstruction_runtime`'s compatibility-adaptation bookkeeping.
    """

    python_version: str


class CollectorOutput(BaseModel):
    """Model-facing evidence package.

    `failing_test_provenance` lets a downstream component (a future
    Diagnoser) know whether this failure was reconstructed from a
    retrospective test overlay WITHOUT ever receiving that overlay's source
    text — see `renacir.collector.context_selection` for the exclusion this
    reflects, and `docs/collector.md` for the full reasoning. For
    `"original_fixture"` cases, the failing test's source may legitimately
    appear in `selected_context` under the normal bounded selection rules;
    for `"reconstructed_retrospective_overlay"` cases, it never does, by
    construction — this asymmetry is deliberate, not an inconsistency.
    """

    case_id: str
    context: ModelFacingContext
    failing_test_provenance: FailingTestProvenance
    exit_code: int
    stdout: str
    stderr: str
    parsed_failure: ParsedFailure
    selected_context: list[SelectedFile]
    repository_structure: list[str]
    runtime: RuntimeInfo
    limits_applied: ContextSelectionLimits
