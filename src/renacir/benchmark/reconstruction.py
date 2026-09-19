"""Reconstruction-recipe execution for real-world (REAL-CI) benchmark cases.

Real cases are never vendored: no upstream production source lives in this
repository. Instead each real `BenchmarkCase.upstream` records a pinned
commit and an explicit `preparation_steps` recipe (clone, checkout, create a
venv, install dependencies) that `prepare_case` executes to materialize a
local, disposable reconstruction cache — see `docs/benchmark_schema.md`.

This module enforces the preparation-vs-evaluation split required by
`docs/research_protocol.md`: `prepare_case` is the only function in Renacir
that may need network access for a real case, and it is idempotent (a
second call is a no-op unless `force=True`). `renacir.benchmark.runner`
never calls it implicitly — evaluating an unprepared real case raises
`PreparationRequiredError` rather than silently reaching the network.
"""

import shutil
import subprocess
from pathlib import Path

from renacir.benchmark.models import BenchmarkCase

DEFAULT_CACHE_ROOT = Path(__file__).resolve().parents[3] / ".benchmark-cache"

_PREPARED_MARKER = ".renacir-prepared"


class PreparationRequiredError(RuntimeError):
    """Raised when a real case is evaluated before `prepare_case` has run."""


def cache_dir(case: BenchmarkCase, cache_root: Path = DEFAULT_CACHE_ROOT) -> Path:
    return cache_root / case.id


def repo_dir(case: BenchmarkCase, cache_root: Path = DEFAULT_CACHE_ROOT) -> Path:
    return cache_dir(case, cache_root) / "repo"


def venv_bin_dir(case: BenchmarkCase, cache_root: Path = DEFAULT_CACHE_ROOT) -> Path:
    return cache_dir(case, cache_root) / "venv" / "bin"


def is_prepared(case: BenchmarkCase, cache_root: Path = DEFAULT_CACHE_ROOT) -> bool:
    return (cache_dir(case, cache_root) / _PREPARED_MARKER).is_file()


def prepare_case(
    case: BenchmarkCase,
    benchmark_root: Path,
    cache_root: Path = DEFAULT_CACHE_ROOT,
    force: bool = False,
) -> Path:
    """Materialize `case`'s reconstructed checkout + venv. Network-requiring.

    Idempotent: a second call with `force=False` (the default) is a no-op if
    the case was already successfully prepared. Never applies the historical
    reference repair and never copies `reference/` into the cache — only the
    documented `preparation_steps` and compatibility adaptations run here.
    """
    if case.upstream is None:
        raise ValueError(f"{case.id}: not a real case (upstream is None), nothing to prepare")

    directory = cache_dir(case, cache_root)
    if force and directory.exists():
        shutil.rmtree(directory)
    elif is_prepared(case, cache_root):
        return directory

    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)

    for step in case.upstream.preparation_steps:
        step_cwd = directory / step.cwd
        subprocess.run(step.argv, cwd=step_cwd, check=True, capture_output=True, text=True)

    repo = repo_dir(case, cache_root)
    git_dir = repo / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir)

    for adaptation in case.upstream.reconstruction_runtime.compatibility_adaptations:
        target = repo / adaptation.file_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(adaptation.file_content)

    (directory / _PREPARED_MARKER).write_text(f"prepared for {case.id}\n")
    return directory
