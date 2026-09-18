import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from renacir.benchmark.discovery import DEFAULT_BENCHMARK_ROOT, case_dir
from renacir.benchmark.models import BenchmarkCase


@dataclass
class CaseResult:
    case_id: str
    pre_patch_passed: bool
    post_patch_passed: bool

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


@contextmanager
def staged_case(case: BenchmarkCase, benchmark_root: Path = DEFAULT_BENCHMARK_ROOT):
    source = case_dir(case, benchmark_root)
    with tempfile.TemporaryDirectory(prefix=f"renacir-benchmark-{case.id}-") as tmp:
        staged = Path(tmp) / "case"
        shutil.copytree(source, staged)
        yield staged


def run_tests(case: BenchmarkCase, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        case.command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )


def apply_reference_repair(case: BenchmarkCase, cwd: Path) -> None:
    patch_path = (cwd / case.reference_repair.patch).resolve()
    subprocess.run(
        ["git", "apply", str(patch_path)],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def evaluate_case(case: BenchmarkCase, benchmark_root: Path = DEFAULT_BENCHMARK_ROOT) -> CaseResult:
    with staged_case(case, benchmark_root) as staged:
        pre_patch = run_tests(case, staged)
        apply_reference_repair(case, staged)
        post_patch = run_tests(case, staged)

    return CaseResult(
        case_id=case.id,
        pre_patch_passed=pre_patch.returncode == 0,
        post_patch_passed=post_patch.returncode == 0,
    )
