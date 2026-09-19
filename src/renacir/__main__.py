import argparse

from renacir.benchmark.discovery import discover_cases
from renacir.collector.collector import UnknownCaseError, collect
from renacir.collector.models import CollectorInput
from renacir.evaluation.retrieval import compute_retrieval_diagnostic


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

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
