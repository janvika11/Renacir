"""Benchmark manifest schema.

Field groups follow the four information tiers documented in
`docs/benchmark_schema.md`:

- Tier A (execution): id, category, path, command, failing_test, `execution`.
- Tier B (potentially model-facing, failure-time only): a strict allowlisted
  subset built separately by `renacir.benchmark.context` — nothing here is
  automatically model-facing just by being a `BenchmarkCase` field.
- Tier C (evaluator-only): `source`, `curation` — read by the harness/analysis
  code, never passed to a future Collector/Diagnoser/Patcher.
- Tier D (reference-repair-only): `reference_repair` and everything under a
  case's `reference/` directory. This is evaluator/reference material, not a
  claim about what a "correct" repair must equal — see
  `docs/research_protocol.md` §7.

Real-world (Phase 2E) cases additionally carry `upstream` (Tier C/D
reconstruction-recipe and provenance metadata — never read by
`renacir.benchmark.context.build_model_facing_context`) and, where the
failing test was introduced by the historical fix commit itself, a
`test_overlay` (Tier D — present for both the pre-repair and post-repair
evaluator runs, but, like `reference/`, never part of the model-visible
staged tree). `upstream` is `None` for every synthetic case; no synthetic
case is ever given fabricated upstream provenance. See
`docs/benchmark_schema.md` for the reconstruction-recipe architecture.
"""

from typing import Literal

from pydantic import BaseModel

FailureCategory = Literal["assertion", "import"]
SourceType = Literal["synthetic", "real"]
FoldAssignment = Literal["unassigned", "dev", "calibration", "test"]
ContaminationRiskFlag = Literal["not_applicable", "unknown", "low", "plausible"]
RealCISubtype = Literal["real_ci_a", "real_ci_b", "real_ci_c"]


class ReferenceRepair(BaseModel):
    """Tier D. Restores a known-good state; not the definition of correctness.

    A benchmark case may have multiple semantically valid repairs. This is
    reference material for restoring passing state, provenance, and
    constructing independent correctness checks — see
    `docs/research_protocol.md` §7.1, which requires no repair to be
    syntactically or structurally similar to this patch to count as correct.
    """

    patch: str


class IndependentCheck(BaseModel):
    """Tier D. An evaluator-only correctness check beyond the originally
    failing test — held-out tests, boundary sweeps, or differential/behavioral
    checks, per `docs/research_protocol.md` §7.1(c). `path` is relative to the
    case directory (e.g. `"reference/independent_check.py"`) and always lives
    under `reference/`, so it is never present in a case's staged directory
    during the pre-repair or post-repair test runs — only copied in
    deliberately, after the reference repair has already been applied, by
    `renacir.benchmark.runner.run_independent_checks`.
    """

    path: str
    description: str


class ExecutionMetadata(BaseModel):
    """Tier A. What's needed to reproduce the case's own runtime, which may
    differ from Renacir's own Python 3.11+ requirement — see
    `docs/research_protocol.md`'s Phase 2 case-specific-runtime decision.
    """

    python_version: str | None = None
    dependency_spec: str | None = None
    install_procedure: str | None = None
    environment_info: str | None = None
    reproducibility_check_version: str


class RepositorySize(BaseModel):
    """Tier C. Descriptive only — not an inclusion gate (Phase 2 revision)."""

    loc: int | None = None
    file_count: int | None = None


class SourceMetadata(BaseModel):
    """Tier C."""

    type: SourceType
    source_group_id: str
    repository_size: RepositorySize | None = None


class ContaminationRisk(BaseModel):
    """Tier C. Risk factors recorded at curation time, not a determination —
    no model is evaluated yet, so no case can be labeled contaminated or
    clean. See `docs/research_protocol.md` §19.
    """

    flag: ContaminationRiskFlag = "unknown"
    notes: str | None = None


class CurationMetadata(BaseModel):
    """Tier C."""

    status: Literal["accepted", "rejected"]
    rejection_reason: str | None = None
    dedup_cluster_id: str
    fold: FoldAssignment = "unassigned"
    contamination_risk: ContaminationRisk = ContaminationRisk()


class CompatibilityAdaptation(BaseModel):
    """Tier C. A modernization shim needed only to reconstruct a runnable
    environment for this case on hardware/interpreters that postdate it —
    never part of the historical bug or its historical repair, and never
    touching the file(s) named in `UpstreamProvenance.production_files`.
    `file_path` is relative to the reconstructed checkout root (e.g.
    `"conftest.py"`); `file_content` is written verbatim by
    `renacir.benchmark.reconstruction.prepare_case` during PREPARATION,
    before any evaluator run. See `docs/benchmark_schema.md`.
    """

    description: str
    reason: str
    file_path: str
    file_content: str


class HistoricalRuntime(BaseModel):
    """Tier C. What's known about the ORIGINAL historical environment the
    bug and its fix occurred in — distinct from `ReconstructionRuntime`,
    the environment actually used to verify this case in this project.
    Fields are `None` where genuinely unknown; never claimed more
    precisely than the primary-source evidence supports.
    """

    python_version: str | None = None
    notes: str | None = None


class PreparationStep(BaseModel):
    """Tier C. One command executed during PREPARATION — the network-
    requiring, one-time (idempotent/cached) step that materializes a real
    case's reconstructed checkout, distinct from evaluation, which must
    remain offline. `argv` is executed directly (never through a shell);
    `cwd` is relative to the case's reconstruction cache root (e.g. `"."`
    or `"repo"`). See `renacir.benchmark.reconstruction.prepare_case`.
    """

    argv: list[str]
    cwd: str = "."


class ReconstructionRuntime(BaseModel):
    """Tier A/C. The environment actually verified this session, plus the
    documented, narrow compatibility adaptations required to run
    historical-era code on it.
    """

    python_version: str
    compatibility_adaptations: list[CompatibilityAdaptation] = []


class RetrospectiveTestOverlay(BaseModel):
    """Tier D. For a real case whose failing test was introduced BY the
    historical fix commit (a retrospective regression test — see the
    REAL-CI-C definition in `docs/research_protocol.md`), this is the test
    file applied for BOTH the pre-repair and post-repair evaluator runs.
    Unlike an ordinarily-vendored test file, it is — like `reference/` —
    never part of the model-visible staged tree; it is copied in only by
    `renacir.benchmark.runner.staged_case`. `path` is relative to the case
    directory and always lives under `reference/`. `target_path` is where
    it lands inside the reconstructed checkout (e.g.
    `"tests/test_renacir_repro.py"`), which must match `failing_test`.
    """

    path: str
    target_path: str


class UpstreamProvenance(BaseModel):
    """Tier C/D. Real-world provenance and reconstruction-recipe metadata
    for a REAL-CI case. `None` of these fields are ever read by
    `renacir.benchmark.context.build_model_facing_context` — see
    `tests/benchmark/test_context.py`. Always `None` on `BenchmarkCase` for
    synthetic cases; no synthetic case is ever given placeholder or
    fabricated values here. See `docs/benchmark_schema.md`.
    """

    repository: str
    repository_url: str
    license: str
    license_verification_note: str
    issue_url: str | None = None
    issue_date: str | None = None
    buggy_commit: str
    fix_commit: str
    fix_date: str | None = None
    production_files: list[str]
    real_ci_subtype: RealCISubtype
    historical_runtime: HistoricalRuntime
    reconstruction_runtime: ReconstructionRuntime
    preparation_steps: list[PreparationStep]
    preparation_requires_network: bool
    evaluation_requires_network: bool
    # Path, relative to the reconstructed checkout root, containing the
    # importable package ("." for a flat layout, "src" for a src layout).
    # Evaluation prepends `<staged checkout>/<package_root>` to PYTHONPATH so
    # the package actually imported is always the one in the freshly staged
    # (pre- or post-repair) copy, never a stale editable-install reference
    # back into the persistent reconstruction cache (see runner._subprocess_env).
    package_root: str = "."


class BenchmarkCase(BaseModel):
    id: str
    category: FailureCategory
    path: str
    command: list[str]
    failing_test: str
    reference_repair: ReferenceRepair
    execution: ExecutionMetadata
    source: SourceMetadata
    curation: CurationMetadata
    independent_checks: list[IndependentCheck] = []
    upstream: UpstreamProvenance | None = None
    test_overlay: RetrospectiveTestOverlay | None = None


class BenchmarkManifest(BaseModel):
    schema_version: int
    cases: list[BenchmarkCase]
