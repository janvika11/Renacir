import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from renacir.benchmark.discovery import DEFAULT_BENCHMARK_ROOT, case_dir
from renacir.benchmark.models import BenchmarkCase
from renacir.benchmark.reconstruction import (
    DEFAULT_CACHE_ROOT,
    PreparationRequiredError,
    is_prepared,
    repo_dir,
    venv_bin_dir,
)

REAL_CASE_TEST_TIMEOUT = 60


@dataclass
class IndependentCheckResult:
    path: str
    passed: bool


@dataclass
class CaseResult:
    case_id: str
    pre_patch_passed: bool
    post_patch_passed: bool
    independent_check_results: list[IndependentCheckResult] = field(default_factory=list)

    @property
    def reproduced_as_expected(self) -> bool:
        """True iff this single run failed pre-repair and passed post-repair.

        One run only. Curation-time reproducibility checking (repeating this
        several times before accepting a case) is a separate procedure — see
        `execution.reproducibility_check_version` in the manifest and
        `docs/benchmark_schema.md`. Neither this property nor that field is a
        statistical guarantee of non-flakiness, only a pragmatic pilot rule.
        """
        return self.pre_patch_passed is False and self.post_patch_passed is True

    @property
    def independent_checks_passed(self) -> bool:
        """True if every independent check passed, vacuously True if none
        were defined for this case (not every case has one — see
        `docs/research_protocol.md` §7.2)."""
        return all(result.passed for result in self.independent_check_results)


@contextmanager
def staged_case(
    case: BenchmarkCase,
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    cache_root: Path = DEFAULT_CACHE_ROOT,
):
    """Stage a case's model-visible files into an isolated temp directory.

    `reference/` (Tier D — the reference repair, any provenance, and
    independent-check files) is deliberately excluded from this copy. It is
    staged in only by `apply_reference_repair` (the patch itself, read
    directly from the original case directory) and `run_independent_checks`
    (individual check files, copied in only after the repair is applied) —
    never as part of the general staged tree. This is what keeps Tier D
    material out of the directory a future Collector would eventually scan,
    independent of whatever `ModelFacingContext` itself does or doesn't
    expose.

    For a real case (`case.upstream is not None`), the general copy comes
    from the already-prepared reconstruction cache (`repo_dir`, which has no
    `.git` — see `reconstruction.prepare_case`) rather than a locally
    vendored fixture directory, and `evaluate_case` must have already called
    `prepare_case`; this raises `PreparationRequiredError` otherwise rather
    than reaching the network.

    Deliberately does NOT apply `case.test_overlay` — a retrospective test
    file must never sit in the general tree this function yields (that tree
    is what a future Collector would call this function to obtain), even
    though `evaluate_case` needs that file present to run the evaluator's
    own pre-/post-repair test passes. See `apply_test_overlay`, which
    `evaluate_case` calls directly on its own private `staged` instance
    rather than through this function, keeping the two concerns separate the
    same way `apply_reference_repair` is applied outside of, not inside,
    `staged_case`.
    """
    if case.upstream is not None:
        if not is_prepared(case, cache_root):
            raise PreparationRequiredError(
                f"{case.id}: real case not prepared. Run "
                f"`python -m renacir.benchmark prepare {case.id}` first "
                "(requires network access) before evaluating it."
            )
        source = repo_dir(case, cache_root)
    else:
        source = case_dir(case, benchmark_root)

    with tempfile.TemporaryDirectory(prefix=f"renacir-benchmark-{case.id}-") as tmp:
        staged = Path(tmp) / "case"
        shutil.copytree(source, staged, ignore=shutil.ignore_patterns("reference"))
        yield staged


def apply_test_overlay(
    case: BenchmarkCase, cwd: Path, benchmark_root: Path = DEFAULT_BENCHMARK_ROOT
) -> None:
    """Copy `case.test_overlay` (Tier D — a retrospective regression test
    introduced by the historical fix commit) into `cwd`, evaluator-side
    only. A no-op if `case.test_overlay` is `None`. Called by `evaluate_case`
    directly, never by `staged_case`, so a caller that only uses
    `staged_case` (e.g. a future Collector) never sees this file — see
    `staged_case`'s docstring.
    """
    if case.test_overlay is None:
        return
    overlay_source = case_dir(case, benchmark_root) / case.test_overlay.path
    overlay_target = cwd / case.test_overlay.target_path
    overlay_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(overlay_source, overlay_target)


def _subprocess_env(
    case: BenchmarkCase, cwd: Path, cache_root: Path = DEFAULT_CACHE_ROOT
) -> dict | None:
    """`None` for synthetic cases (ambient PATH is fine). For a real case,
    prepends the reconstruction cache's own venv so `case.command` (e.g.
    `["pytest", ...]`) resolves to the pinned/reconstructed dependencies
    installed during `prepare_case`, and prepends `PYTHONPATH` with
    `cwd`'s own `upstream.package_root` so the package actually imported is
    always the one in the freshly staged (pre- or post-repair) copy — never
    a stale editable-install reference back into the persistent
    reconstruction cache.
    """
    if case.upstream is None:
        return None
    env = os.environ.copy()
    env["PATH"] = f"{venv_bin_dir(case, cache_root)}{os.pathsep}{env['PATH']}"
    package_root = str((cwd / case.upstream.package_root).resolve())
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{package_root}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else package_root
    )
    return env


def run_tests(
    case: BenchmarkCase,
    cwd: Path,
    cache_root: Path = DEFAULT_CACHE_ROOT,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Run `case.command`, optionally with `extra_args` appended (e.g. a
    reduced-traceback-verbosity flag) — never mutates `case.command` itself,
    only what's passed to this specific subprocess invocation. Used by
    `renacir.collector` to request `--tb=line` for reconstructed real cases
    without changing the benchmark's own evaluate_case behavior (default
    `[]` is a no-op, identical to the pre-existing signature).
    """
    timeout = REAL_CASE_TEST_TIMEOUT if case.upstream is not None else 30
    return subprocess.run(
        [*case.command, *(extra_args or [])],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_subprocess_env(case, cwd, cache_root),
    )


def apply_reference_repair(
    case: BenchmarkCase, cwd: Path, benchmark_root: Path = DEFAULT_BENCHMARK_ROOT
) -> None:
    """Apply the reference-repair patch, read from the original (non-staged)
    case directory — `reference/` is never staged, so the patch file is
    located there directly rather than inside `cwd`.
    """
    patch_path = case_dir(case, benchmark_root) / case.reference_repair.patch
    subprocess.run(
        ["git", "apply", str(patch_path.resolve())],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def run_independent_checks(
    case: BenchmarkCase,
    cwd: Path,
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> list[IndependentCheckResult]:
    """Run each of a case's independent correctness checks against the
    already-repaired code in `cwd`. Each check file is copied in from the
    original case directory's `reference/`, one at a time, and executed
    explicitly by filename — never auto-discovered by a bare `pytest -q`
    collection pass, and never present during the pre-repair run.
    """
    results = []
    source_dir = case_dir(case, benchmark_root)
    for check in case.independent_checks:
        source_file = source_dir / check.path
        dest_file = cwd / Path(check.path).name
        shutil.copy(source_file, dest_file)
        proc = subprocess.run(
            ["pytest", dest_file.name, "-q"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=REAL_CASE_TEST_TIMEOUT if case.upstream is not None else 30,
            env=_subprocess_env(case, cwd, cache_root),
        )
        results.append(IndependentCheckResult(path=check.path, passed=proc.returncode == 0))
    return results


def evaluate_case(
    case: BenchmarkCase,
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> CaseResult:
    with staged_case(case, benchmark_root, cache_root) as staged:
        apply_test_overlay(case, staged, benchmark_root)
        pre_patch = run_tests(case, staged, cache_root)
        apply_reference_repair(case, staged, benchmark_root)
        post_patch = run_tests(case, staged, cache_root)
        check_results = run_independent_checks(case, staged, benchmark_root, cache_root)

    return CaseResult(
        case_id=case.id,
        pre_patch_passed=pre_patch.returncode == 0,
        post_patch_passed=post_patch.returncode == 0,
        independent_check_results=check_results,
    )
