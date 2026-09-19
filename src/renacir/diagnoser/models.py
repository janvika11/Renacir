"""Diagnoser input/output schema.

`DiagnoserInput` is an explicit allowlist built from `CollectorOutput` by
`renacir.diagnoser.diagnoser.build_diagnoser_input()` — `CollectorOutput`
itself is never passed to a provider. See `docs/diagnoser.md` for the full
boundary rationale.

Deliberate exclusion, corrected from the Phase 4A proposal: `category`
(benchmark taxonomy metadata — `"assertion"` | `"import"`) is NOT a
`DiagnoserInput` field. It provides no necessary diagnostic information
beyond what `parsed_failure`/`stdout`/`stderr`/visible source already carry,
and a real CI failure would never come pre-labeled with it. It remains
available evaluator-side via `BenchmarkCase.category` for analysis, but is
never model-facing.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from renacir.collector.models import ParsedFailure, RuntimeInfo, SelectedFile

InputCondition = Literal["failure_output_only", "full_context"]
ParseStatus = Literal["ok", "parse_error", "validation_error", "provider_error"]

# Explicit, stated bounds — malformed or oversized provider output must be
# rejected (raising a ValidationError, recorded as parse_status
# "validation_error") rather than silently accepted into an experiment record.
_MAX_ROOT_CAUSE_CHARS = 2000
_MAX_REASONING_CHARS = 4000
_MAX_LIST_ITEMS = 20
_MAX_PATH_CHARS = 500
_MAX_SYMBOL_CHARS = 200

BoundedPath = Annotated[str, StringConstraints(max_length=_MAX_PATH_CHARS)]
BoundedSymbol = Annotated[str, StringConstraints(max_length=_MAX_SYMBOL_CHARS)]


class DiagnoserInput(BaseModel):
    """Model-visible only. Every field here is safe to render into a prompt —
    nothing evaluator-only, nothing from `reference/`, no benchmark taxonomy
    labels. See `renacir.diagnoser.diagnoser.build_diagnoser_input`.
    """

    failing_test: str
    command: list[str]
    repository_identity: str | None
    exit_code: int
    stdout: str
    stderr: str
    parsed_failure: ParsedFailure
    selected_context: list[SelectedFile]
    repository_structure: list[str]
    runtime: RuntimeInfo


class Diagnosis(BaseModel):
    """Strict output schema. No patch, no diff, no replacement code, no
    repair-instruction field — checked structurally by
    `tests/diagnoser/test_models.py`, not left to prompt-following alone.
    """

    root_cause_summary: Annotated[str, StringConstraints(max_length=_MAX_ROOT_CAUSE_CHARS)]
    suspected_files: Annotated[list[BoundedPath], Field(max_length=_MAX_LIST_ITEMS)] = []
    suspected_symbols: Annotated[list[BoundedSymbol], Field(max_length=_MAX_LIST_ITEMS)] = []
    reasoning_summary: Annotated[str, StringConstraints(max_length=_MAX_REASONING_CHARS)]
    diagnosis_confidence: float = Field(ge=0.0, le=1.0)
    insufficient_context: bool


class DiagnosisRunRecord(BaseModel):
    """One structured record per Diagnoser invocation. Schema supports
    repeated runs (`run_id` distinguishes attempts) without choosing or
    encoding K anywhere.
    """

    case_id: str
    condition: InputCondition
    run_id: str
    provider: str
    model: str
    prompt_version: str
    temperature: float
    max_tokens: int
    timestamp: datetime
    renacir_commit: str
    input_fingerprint: str
    rendered_system_prompt: str
    rendered_user_prompt: str
    raw_response: str | None
    parsed_diagnosis: Diagnosis | None
    parse_status: ParseStatus
    provider_error: str | None
    grounding_violation: bool
    latency_seconds: float | None
    input_tokens: int | None
    output_tokens: int | None

    # Generic, provider-agnostic bag for extra reproducibility metadata a
    # given provider adapter may have available (e.g. Ollama's exact model
    # digest/quantization) — never required, never assumed to have any
    # specific keys, and never populated with model-family-specific logic
    # in the Diagnoser core itself. Empty for providers with nothing extra
    # to record (e.g. Anthropic, where the model string is already exact).
    model_metadata: dict[str, str] = {}
