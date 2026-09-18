import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from renacir.benchmark.discovery import DEFAULT_BENCHMARK_ROOT, case_dir
from renacir.benchmark.models import BenchmarkCase


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
def staged_case(case: BenchmarkCase, benchmark_root: Path = DEFAULT_BENCHMARK_ROOT):
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
    """
    source = case_dir(case, benchmark_root)
    with tempfile.TemporaryDirectory(prefix=f"renacir-benchmark-{case.id}-") as tmp:
        staged = Path(tmp) / "case"
        shutil.copytree(source, staged, ignore=shutil.ignore_patterns("reference"))
        yield staged


def run_tests(case: BenchmarkCase, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        case.command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
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
    case: BenchmarkCase, cwd: Path, benchmark_root: Path = DEFAULT_BENCHMARK_ROOT
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
            timeout=30,
        )
        results.append(IndependentCheckResult(path=check.path, passed=proc.returncode == 0))
    return results


def evaluate_case(case: BenchmarkCase, benchmark_root: Path = DEFAULT_BENCHMARK_ROOT) -> CaseResult:
    with staged_case(case, benchmark_root) as staged:
        pre_patch = run_tests(case, staged)
        apply_reference_repair(case, staged, benchmark_root)
        post_patch = run_tests(case, staged)
        check_results = run_independent_checks(case, staged, benchmark_root)

    return CaseResult(
        case_id=case.id,
        pre_patch_passed=pre_patch.returncode == 0,
        post_patch_passed=post_patch.returncode == 0,
        independent_check_results=check_results,
    )
