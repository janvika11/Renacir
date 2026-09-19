"""Diagnoser orchestration.

CollectorOutput -> DiagnoserInput (explicit allowlist) -> versioned rendered
prompt -> LLMProvider.generate() (called exactly once, no retry) -> strict
Diagnosis parsing/validation -> grounding check -> DiagnosisRunRecord.

Deliberately takes only a `case_id: str`, never a `BenchmarkCase` object —
this module never holds a reference to `case.reference_repair`,
`case.independent_checks`, `case.upstream`, `case.curation`, or
`case.test_overlay`, so it cannot leak from them even by accident. No patch
generation, no tools, no loops, no agent framework.
"""

import hashlib
import json
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from renacir.collector.models import CollectorOutput
from renacir.diagnoser.models import DiagnoserInput, Diagnosis, DiagnosisRunRecord, InputCondition
from renacir.diagnoser.prompts.v1 import PROMPT_VERSION, SYSTEM_PROMPT, render_user_prompt
from renacir.diagnoser.provider import LLMProvider, LLMRequest


def build_diagnoser_input(output: CollectorOutput, condition: InputCondition) -> DiagnoserInput:
    """Explicit allowlist from `CollectorOutput` — `CollectorOutput` itself
    is never passed to a provider. `category` is deliberately excluded (a
    Phase 4B correction to the Phase 4A proposal) even though
    `ModelFacingContext` carries it.
    """
    if condition == "failure_output_only":
        selected_context: list = []
        repository_structure: list[str] = []
    else:
        selected_context = output.selected_context
        repository_structure = output.repository_structure

    return DiagnoserInput(
        failing_test=output.context.failing_test,
        command=output.context.command,
        repository_identity=output.context.repository_identity,
        exit_code=output.exit_code,
        stdout=output.stdout,
        stderr=output.stderr,
        parsed_failure=output.parsed_failure,
        selected_context=selected_context,
        repository_structure=repository_structure,
        runtime=output.runtime,
    )


def fingerprint_request(system_prompt: str, user_prompt: str) -> str:
    """SHA-256 over the exact model-visible rendered request. Never includes
    a secret — there is none in this material to include.
    """
    digest = hashlib.sha256()
    digest.update(system_prompt.encode("utf-8"))
    digest.update(b"\n---\n")
    digest.update(user_prompt.encode("utf-8"))
    return digest.hexdigest()


def _renacir_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _grounding_violation(diagnosis: Diagnosis, diagnoser_input: DiagnoserInput) -> bool:
    """A `suspected_files` entry is grounded if it's a path the model
    actually saw: selected-context content, a traceback frame, or a bare
    repository-structure filename listing (seen as a name, even without
    content). Anything else is a violation — the model cited a file it was
    never shown.
    """
    visible_paths = (
        {f.path for f in diagnoser_input.selected_context}
        | {frame.file for frame in diagnoser_input.parsed_failure.frames if frame.file}
        | set(diagnoser_input.repository_structure)
    )
    return any(path not in visible_paths for path in diagnosis.suspected_files)


def diagnose(
    case_id: str,
    output: CollectorOutput,
    condition: InputCondition,
    provider: LLMProvider,
    model: str,
    temperature: float,
    max_tokens: int,
    run_id: str | None = None,
    model_metadata: dict[str, str] | None = None,
) -> DiagnosisRunRecord:
    diagnoser_input = build_diagnoser_input(output, condition)
    user_prompt = render_user_prompt(diagnoser_input)
    request = LLMRequest(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    input_fingerprint = fingerprint_request(SYSTEM_PROMPT, user_prompt)

    response = provider.generate(request)  # exactly once — no retry, no repair call

    parsed_diagnosis: Diagnosis | None = None
    grounding_violation = False

    if response.provider_error is not None or response.raw_text is None:
        parse_status = "provider_error"
    else:
        try:
            data = json.loads(response.raw_text)
        except json.JSONDecodeError:
            parse_status = "parse_error"
        else:
            try:
                parsed_diagnosis = Diagnosis.model_validate(data)
            except ValidationError:
                parse_status = "validation_error"
            else:
                parse_status = "ok"
                grounding_violation = _grounding_violation(parsed_diagnosis, diagnoser_input)

    return DiagnosisRunRecord(
        case_id=case_id,
        condition=condition,
        run_id=run_id or str(uuid.uuid4()),
        provider=type(provider).__name__,
        model=model,
        prompt_version=PROMPT_VERSION,
        temperature=temperature,
        max_tokens=max_tokens,
        timestamp=datetime.now(UTC),
        renacir_commit=_renacir_commit(),
        input_fingerprint=input_fingerprint,
        rendered_system_prompt=SYSTEM_PROMPT,
        rendered_user_prompt=user_prompt,
        raw_response=response.raw_text,
        parsed_diagnosis=parsed_diagnosis,
        parse_status=parse_status,
        provider_error=response.provider_error,
        grounding_violation=grounding_violation,
        latency_seconds=response.latency_seconds,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        model_metadata=model_metadata or {},
    )


def save_run_record(record: DiagnosisRunRecord, output_dir: Path) -> Path:
    """Persist one `DiagnosisRunRecord` as JSON — no database, no ground-
    truth claim. `output_dir` is expected to be a git-ignored local
    directory (e.g. `artifacts/diagnosis_runs/`). Never writes a secret:
    the record itself structurally never contains one (no field for an API
    key exists anywhere in this schema).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{record.run_id}.json"
    path.write_text(record.model_dump_json(indent=2))
    return path
