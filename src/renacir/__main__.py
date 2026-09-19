import argparse
import sys
from pathlib import Path

from renacir.benchmark.discovery import discover_cases
from renacir.collector.collector import UnknownCaseError, collect
from renacir.collector.models import CollectorInput
from renacir.config import settings
from renacir.diagnoser.diagnoser import (
    build_diagnoser_input,
    diagnose,
    fingerprint_request,
    save_run_record,
)
from renacir.diagnoser.prompts.v1 import PROMPT_VERSION, SYSTEM_PROMPT, render_user_prompt
from renacir.diagnoser.providers.anthropic import AnthropicConfigurationError, AnthropicProvider
from renacir.diagnoser.providers.ollama import OllamaProvider, fetch_model_metadata
from renacir.evaluation.diagnosis import score_suspected_files
from renacir.evaluation.retrieval import compute_retrieval_diagnostic

DEFAULT_RUN_RECORD_DIR = Path("artifacts/diagnosis_runs")


def cmd_collect(args: argparse.Namespace) -> int:
    try:
        output = collect(CollectorInput(case_id=args.case_id))
    except UnknownCaseError as exc:
        print(str(exc))
        return 1

    print(f"case: {output.case_id}  (failing_test_provenance: {output.failing_test_provenance})")
    print(f"exit_code: {output.exit_code}")
    print()
    print("parsed failure:")
    print(f"  error_type:    {output.parsed_failure.error_type}")
    print(f"  error_message: {output.parsed_failure.error_message}")
    print(f"  summary:       {output.parsed_failure.summary}")
    print(f"  frames:        {len(output.parsed_failure.frames)}")
    for frame in output.parsed_failure.frames:
        print(f"    {frame.file}:{frame.line} in {frame.function}")
    print()
    n_files = len(output.selected_context)
    max_files = output.limits_applied.max_files
    print(f"selected context ({n_files}/{max_files} files):")
    for f in output.selected_context:
        print(f"  {f.path}  ({len(f.content)} chars, reason={f.reason}, truncated={f.truncated})")
    print()
    print(f"runtime: Python {output.runtime.python_version}")

    # Evaluator-only: computed strictly AFTER collection, from the benchmark
    # case's reference repair. Never influences the CollectorOutput above —
    # see renacir.evaluation.retrieval's module docstring.
    case = next(c for c in discover_cases() if c.id == output.case_id)
    diagnostic = compute_retrieval_diagnostic(output, case)
    print()
    print("retrieval diagnostic (evaluator-only, computed after collection):")
    print(f"  empty_context:                       {diagnostic.empty_context}")
    print(f"  truncation_occurred:                  {diagnostic.truncation_occurred}")
    print(
        f"  reference_relevant_files_available:   {diagnostic.reference_relevant_files_available}"
    )
    print(
        f"  reference_relevant_files_retrieved:   {diagnostic.reference_relevant_files_retrieved}"
    )
    print(f"  reference_relevant_files_total:       {diagnostic.reference_relevant_files_total}")
    print(f"  reference_relevant_file_recall:       {diagnostic.reference_relevant_file_recall}")

    if args.json:
        print()
        print(output.model_dump_json(indent=2))
        print()
        print("(evaluator-only, not part of CollectorOutput):")
        print(diagnostic.model_dump_json(indent=2))
    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    try:
        case = next(c for c in discover_cases() if c.id == args.case_id)
    except StopIteration:
        print(f"unknown case id: {args.case_id}", file=sys.stderr)
        return 1

    model = args.model or settings.llm_model
    if not model:
        print(
            "no model specified: pass --model or set LLM_MODEL in the environment/.env. "
            "There is no default model.",
            file=sys.stderr,
        )
        return 1

    if not args.allow_api_call:
        reason = (
            "a real, paid Anthropic API call"
            if args.provider == "anthropic"
            else "a real local Ollama inference call"
        )
        print(
            f"refusing: this would make {reason}. "
            "Pass --allow-api-call to proceed. This is a safety/cost guard, not an "
            "experimental variable.",
            file=sys.stderr,
        )
        return 1

    model_metadata: dict[str, str] = {}
    if args.provider == "anthropic":
        try:
            provider = AnthropicProvider(api_key=settings.anthropic_api_key or "")
        except AnthropicConfigurationError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    elif args.provider == "ollama":
        provider = OllamaProvider()
        # Evaluator/reproducibility-side only — never part of LLMRequest,
        # never influences the call itself. Fetched before the call so a
        # failure here is visible pre-call rather than silently absent.
        model_metadata = fetch_model_metadata(model)
    else:
        # unreachable given choices=["anthropic", "ollama"], kept explicit
        # for when another provider is added
        print(f"unsupported provider: {args.provider}", file=sys.stderr)
        return 1

    output = collect(CollectorInput(case_id=case.id))
    diagnoser_input = build_diagnoser_input(output, args.condition)
    user_prompt = render_user_prompt(diagnoser_input)
    fingerprint = fingerprint_request(SYSTEM_PROMPT, user_prompt)

    print("--- pre-call metadata (no secrets) ---")
    print(f"case_id: {case.id}")
    print(f"condition: {args.condition}")
    print(f"model-visible files: {[f.path for f in diagnoser_input.selected_context] or '(none)'}")
    print(f"prompt_version: {PROMPT_VERSION}")
    print(f"prompt fingerprint: {fingerprint}")
    print(f"model: {model}")
    if model_metadata:
        print(f"model_metadata: {model_metadata}")
    print(f"temperature: {args.temperature}")
    print(f"max_tokens: {args.max_tokens}")
    print()
    print(f">>> making exactly one real {args.provider} call now <<<")

    record = diagnose(
        case.id,
        output,
        args.condition,
        provider,
        model=model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        model_metadata=model_metadata,
    )

    print()
    print("--- result ---")
    print(f"parse_status: {record.parse_status}")
    print(f"provider_error: {record.provider_error}")
    if record.parsed_diagnosis is not None:
        d = record.parsed_diagnosis
        print(f"root_cause_summary: {d.root_cause_summary}")
        print(f"suspected_files: {d.suspected_files}")
        print(f"suspected_symbols: {d.suspected_symbols}")
        print(f"reasoning_summary: {d.reasoning_summary}")
        print(f"diagnosis_confidence: {d.diagnosis_confidence}")
        print(f"insufficient_context: {d.insufficient_context}")
    print(f"grounding_violation: {record.grounding_violation}")
    print(f"latency_seconds: {record.latency_seconds}")
    print(f"input_tokens: {record.input_tokens}")
    print(f"output_tokens: {record.output_tokens}")

    saved_path = save_run_record(record, DEFAULT_RUN_RECORD_DIR)
    print()
    print(f"run record saved: {saved_path}")

    # Evaluator-only, computed strictly AFTER the record is frozen — never
    # fed back into the request that already happened.
    score = score_suspected_files(record, case)
    print()
    print("evaluator-side suspected-file localization (computed after the fact):")
    print(f"  reference_files_available: {score.reference_files_available}")
    print(f"  precision: {score.precision}")
    print(f"  recall: {score.recall}")
    print(f"  f1: {score.f1}")

    if args.json:
        print()
        print(record.model_dump_json(indent=2))

    return 0 if record.parse_status == "ok" else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m renacir")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser(
        "collect", help="run the Collector against a benchmark case and inspect its output"
    )
    collect_parser.add_argument("case_id", help="benchmark case id")
    collect_parser.add_argument(
        "--json", action="store_true", help="also print the full CollectorOutput as JSON"
    )
    collect_parser.set_defaults(func=cmd_collect)

    diagnose_parser = subparsers.add_parser(
        "diagnose",
        help="run the Diagnoser (real calls require --allow-api-call)",
    )
    diagnose_parser.add_argument("case_id", help="benchmark case id")
    diagnose_parser.add_argument(
        "--condition", choices=["failure_output_only", "full_context"], required=True
    )
    diagnose_parser.add_argument("--provider", choices=["anthropic", "ollama"], required=True)
    diagnose_parser.add_argument(
        "--model",
        default=None,
        help="exact model id/tag (falls back to LLM_MODEL env var; no default)",
    )
    diagnose_parser.add_argument("--temperature", type=float, default=0.0)
    diagnose_parser.add_argument("--max-tokens", type=int, default=1024)
    diagnose_parser.add_argument(
        "--allow-api-call",
        action="store_true",
        help="required to actually contact a provider — a real API call, paid or local",
    )
    diagnose_parser.add_argument(
        "--json", action="store_true", help="also print the full DiagnosisRunRecord as JSON"
    )
    diagnose_parser.set_defaults(func=cmd_diagnose)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
