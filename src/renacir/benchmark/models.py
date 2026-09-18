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
"""

from typing import Literal

from pydantic import BaseModel

FailureCategory = Literal["assertion", "import"]
SourceType = Literal["synthetic", "real"]
FoldAssignment = Literal["unassigned", "dev", "calibration", "test"]
ContaminationRiskFlag = Literal["not_applicable", "unknown", "low", "plausible"]


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


class BenchmarkManifest(BaseModel):
    schema_version: int
    cases: list[BenchmarkCase]
