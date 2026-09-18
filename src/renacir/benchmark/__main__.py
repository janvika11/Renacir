import argparse
import json
import sys

from renacir.benchmark.discovery import discover_cases
from renacir.benchmark.runner import evaluate_case


def cmd_list(_args: argparse.Namespace) -> int:
    for case in discover_cases():
        print(f"{case.id}\t{case.category}\t{case.path}")
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
        if not result.reproduced_as_expected:
            exit_code = 1
        print(
            json.dumps(
                {
                    "case_id": result.case_id,
                    "pre_patch_passed": result.pre_patch_passed,
                    "post_patch_passed": result.post_patch_passed,
                    "reproduced_as_expected": result.reproduced_as_expected,
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

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
