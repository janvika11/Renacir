"""Tier B: the explicit, allowlisted subset of a benchmark case that a future
Collector implementation may expose to Diagnoser/Patcher.

This module exists so "what the model can see" is enforced by an allowlist at
the type level, not by convention or by where a file happens to live.
`ModelFacingContext` intentionally has no field that reads from a case's
`reference/` directory (Tier D) and no field that overlaps with the
evaluator-only Tier C metadata (`SourceMetadata`, `CurationMetadata`,
`ContaminationRisk`). See `docs/benchmark_schema.md`.

Collector does not exist yet — nothing here calls or assumes one. This module
only fixes the shape a future Collector must build its output into.
"""

from pydantic import BaseModel

from renacir.benchmark.models import BenchmarkCase, FailureCategory


class ModelFacingContext(BaseModel):
    """Tier B — potentially model-facing, failure-time information only.

    Repository/library identity exposure is an explicit, unresolved design
    variable (`docs/research_protocol.md`, Phase 2 revision) — not decided
    here. `repository_identity` defaults to `None`; a future Collector must
    set it deliberately, never inherit it implicitly from the full case.
    """

    failing_test: str
    command: list[str]
    category: FailureCategory
    repository_identity: str | None = None


def build_model_facing_context(case: BenchmarkCase) -> ModelFacingContext:
    """Construct the Tier B view of a case by explicit allowlisting.

    Reads only `BenchmarkCase.failing_test`, `.command`, and `.category` —
    never `.reference_repair`, `.source`, or `.curation`.
    """
    return ModelFacingContext(
        failing_test=case.failing_test,
        command=case.command,
        category=case.category,
        repository_identity=None,
    )
