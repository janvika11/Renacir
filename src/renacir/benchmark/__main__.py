import argparse
import json
import sys

from renacir.benchmark.discovery import DEFAULT_BENCHMARK_ROOT, discover_cases
from renacir.benchmark.reconstruction import prepare_case
from renacir.benchmark.runner import evaluate_case


def cmd_list(_args: argparse.Namespace) -> int:
    for case in discover_cases():
        provenance = "real" if case.upstream is not None else "synthetic"
        print(f"{case.id}\t{case.category}\t{provenance}\t{case.path}")
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    """Network-requiring, one-time setup for real (reconstruction-recipe)
    cases. No-op for synthetic cases and for already-prepared real cases
    unless `--force` is given. Never applied implicitly by `run`."""
    cases = [c for c in discover_cases() if c.upstream is not None]
    if args.case_id:
        cases = [c for c in cases if c.id == args.case_id]
        if not cases:
            print(f"unknown real case id: {args.case_id}", file=sys.stderr)
            return 1

    for case in cases:
        directory = prepare_case(case, DEFAULT_BENCHMARK_ROOT, force=args.force)
        print(f"{case.id}\tprepared\t{directory}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cases = discover_cases()
    if args.case_id:
        cases = [c for c in cases if c.id == args.case_id]
        if not cases:
            print(f"unknown case id: {args.case_id}", file=sys.stderr)
            return 1

    exit_code = 0
    for case in cases:
        result = evaluate_case(case)
        if not result.reproduced_as_expected or not result.independent_checks_passed:
            exit_code = 1
        print(
            json.dumps(
                {
                    "case_id": result.case_id,
                    "pre_patch_passed": result.pre_patch_passed,
                    "post_patch_passed": result.post_patch_passed,
                    "reproduced_as_expected": result.reproduced_as_expected,
                    "independent_checks": [
                        {"path": r.path, "passed": r.passed}
                        for r in result.independent_check_results
                    ],
                    "independent_checks_passed": result.independent_checks_passed,
                }
            )
        )
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m renacir.benchmark")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="list all benchmark cases").set_defaults(func=cmd_list)

    run_parser = subparsers.add_parser("run", help="run one or all benchmark cases")
    run_parser.add_argument("case_id", nargs="?", help="case id to run (default: all)")
    run_parser.set_defaults(func=cmd_run)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="materialize real cases' reconstructed checkouts (requires network)",
    )
    prepare_parser.add_argument(
        "case_id", nargs="?", help="real case id to prepare (default: all real cases)"
    )
    prepare_parser.add_argument(
        "--force", action="store_true", help="re-prepare even if already cached"
    )
    prepare_parser.set_defaults(func=cmd_prepare)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
