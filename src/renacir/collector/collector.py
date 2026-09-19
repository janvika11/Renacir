"""Collector orchestration: stage a benchmark/reconstructed case, run its
failing test, and package deterministic, bounded, model-facing evidence.

Reuses the existing benchmark staging/execution infrastructure
(`renacir.benchmark.runner`) rather than duplicating it. Never calls
`apply_reference_repair` or `run_independent_checks` — Collector only ever
observes the FAILING state, never the repaired one, and never touches
evaluator-only correctness checks.
"""

import re
import shutil
import sys
import tempfile
from pathlib import Path

from renacir.benchmark.context import build_model_facing_context
from renacir.benchmark.discovery import DEFAULT_BENCHMARK_ROOT, discover_cases
from renacir.benchmark.models import BenchmarkCase
from renacir.benchmark.reconstruction import DEFAULT_CACHE_ROOT
from renacir.benchmark.runner import apply_test_overlay, run_tests, staged_case
from renacir.collector.context_selection import select_context
from renacir.collector.models import CollectorInput, CollectorOutput, ParsedFailure, RuntimeInfo
from renacir.collector.parsing import parse_failure

_PYTEST_VERSION_HEADER = re.compile(r"Python (\d+\.\d+\.\d+)")

_REPOSITORY_STRUCTURE_LIMIT = 200

_SYSTEM_TMP_PREFIX = re.escape(str(Path(tempfile.gettempdir()).resolve()))
_RESIDUAL_TMP_PATH = re.compile(_SYSTEM_TMP_PREFIX + r"/[^\s'\"]*")


class UnknownCaseError(ValueError):
    pass


def _find_case(case_id: str) -> BenchmarkCase:
    for case in discover_cases():
        if case.id == case_id:
            return case
    raise UnknownCaseError(f"unknown case id: {case_id}")


_STRUCTURE_EXCLUDED_DIR_NAMES = {"__pycache__", ".pytest_cache", ".git"}


def _list_repository_structure(root: Path, limit: int = _REPOSITORY_STRUCTURE_LIMIT) -> list[str]:
    names = []
    for path in sorted(root.rglob("*")):
        if _STRUCTURE_EXCLUDED_DIR_NAMES & set(path.relative_to(root).parts):
            continue
        if path.is_file():
            names.append(str(path.relative_to(root)))
        if len(names) >= limit:
            break
    return names


def _observed_python_version(stdout: str) -> str:
    match = _PYTEST_VERSION_HEADER.search(stdout)
    return match.group(1) if match else sys.version.split()[0]


def _redact_host_paths(text: str | None, staged_root: Path, cache_root: Path) -> str | None:
    """Replace the staged tempdir's and reconstruction cache's absolute host
    paths with stable placeholders, for DISPLAY/storage only. `staged_case`
    uses a randomized tempdir suffix per call, so any raw absolute path
    pointing into it (e.g. Python's own `ImportError` message text, which
    embeds the module's absolute file path) would otherwise make two
    collections of the *same* case produce different `CollectorOutput`
    strings — breaking determinism — and would incidentally reveal local
    filesystem layout.

    Applied AFTER `parse_failure` has already run on the original,
    unredacted text — `parse_failure` needs real absolute paths to resolve
    frames via `Path.relative_to` (see `parsing._normalize_frame_path`);
    redacting first would turn `<case-root>/httpie/sessions.py` into an
    unresolvable literal and silently empty out context selection (found and
    fixed during implementation — see the Phase 3 report).

    A residual catch-all also redacts anything still pointing under the
    system temp root (`tempfile.gettempdir()`) after the two specific
    substitutions above — found necessary because pytest's own `tmp_path`
    fixture (used inside `click-path-resolve-symlink`'s test) embeds an
    absolute path containing the local OS username and a run counter
    (e.g. `/private/var/.../pytest-of-<user>/pytest-129/...`), which is
    neither `staged_root` nor `cache_root` but is exactly as
    non-deterministic and host-revealing.
    """
    if text is None:
        return None
    text = text.replace(str(staged_root.resolve()), "<case-root>")
    text = text.replace(str(cache_root.resolve()), "<reconstruction-cache>")
    text = _RESIDUAL_TMP_PATH.sub("<tmp>", text)
    return text


def _redact_parsed_failure(
    parsed: ParsedFailure, staged_root: Path, cache_root: Path
) -> ParsedFailure:
    return parsed.model_copy(
        update={
            "error_message": _redact_host_paths(parsed.error_message, staged_root, cache_root),
            "summary": _redact_host_paths(parsed.summary, staged_root, cache_root),
        }
    )


def _purge_stale_caches(staged_root: Path) -> None:
    """Delete any `__pycache__`/`.pytest_cache` directories copied into the
    staged tree from the original fixture. Stale `.pyc` bytecode compiled
    during an earlier direct `pytest -q` run in the fixture directory (see
    README.md's "reproduce a fixture's failure by hand" workflow) embeds the
    fixture's own absolute host path in its debug info; if reused (mtime is
    preserved by `shutil.copytree`), pytest's traceback trailer prints that
    absolute path instead of a path relative to this run's staged copy —
    leaking local filesystem layout and defeating `_within_case_root`
    filtering. Scoped to Collector's own private staged copy only — never
    touches the original fixture or `renacir.benchmark.runner`'s shared
    `staged_case` behavior.
    """
    for name in ("__pycache__", ".pytest_cache"):
        for path in staged_root.rglob(name):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)


def collect(
    collector_input: CollectorInput,
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> CollectorOutput:
    case = _find_case(collector_input.case_id)
    limits = collector_input.limits
    is_reconstructed = case.test_overlay is not None

    # For a reconstructed real case, request pytest's condensed one-line
    # traceback format so raw stdout never echoes the retrospective test
    # overlay's own source lines (its default multi-line report shows the
    # failing call's source context, which would otherwise leak overlay
    # content through stdout regardless of what select_context() does).
    extra_args = ["--tb=line"] if is_reconstructed else None

    with staged_case(case, benchmark_root, cache_root) as staged:
        _purge_stale_caches(staged)
        apply_test_overlay(case, staged, benchmark_root)
        result = run_tests(case, staged, cache_root, extra_args=extra_args)

        # Parse against the ORIGINAL, unredacted stdout — frame-path
        # normalization needs real absolute paths (see
        # `_redact_host_paths`'s docstring). Redaction happens afterward,
        # applied only to what's stored/displayed.
        parsed = parse_failure(result.stdout, staged)
        selected_context = select_context(staged, case, parsed, limits)
        repository_structure = _list_repository_structure(staged)
        python_version = _observed_python_version(result.stdout)

        stdout = _redact_host_paths(result.stdout, staged, cache_root)
        stderr = _redact_host_paths(result.stderr, staged, cache_root)
        parsed = _redact_parsed_failure(parsed, staged, cache_root)

    return CollectorOutput(
        case_id=case.id,
        context=build_model_facing_context(case),
        failing_test_provenance=(
            "reconstructed_retrospective_overlay" if is_reconstructed else "original_fixture"
        ),
        exit_code=result.returncode,
        stdout=stdout[: limits.max_stdout_chars],
        stderr=stderr[: limits.max_stderr_chars],
        parsed_failure=parsed,
        selected_context=selected_context,
        repository_structure=repository_structure,
        runtime=RuntimeInfo(python_version=python_version),
        limits_applied=limits,
    )
