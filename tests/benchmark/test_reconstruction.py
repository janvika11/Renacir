import subprocess

import pytest

from renacir.benchmark.discovery import DEFAULT_BENCHMARK_ROOT, discover_cases
from renacir.benchmark.reconstruction import cache_dir, is_prepared, prepare_case, repo_dir


def _a_real_case():
    return next(c for c in discover_cases() if c.upstream is not None)


def test_is_prepared_is_false_for_a_fresh_cache_root(tmp_path):
    case = _a_real_case()
    assert is_prepared(case, cache_root=tmp_path) is False


def test_cache_dir_is_deterministic_per_case_id(tmp_path):
    case = _a_real_case()
    assert cache_dir(case, cache_root=tmp_path) == tmp_path / case.id
    assert repo_dir(case, cache_root=tmp_path) == tmp_path / case.id / "repo"


def test_prepare_case_raises_for_a_synthetic_case(tmp_path):
    synthetic_case = next(c for c in discover_cases() if c.upstream is None)
    with pytest.raises(ValueError, match="not a real case"):
        prepare_case(synthetic_case, DEFAULT_BENCHMARK_ROOT, cache_root=tmp_path)


def test_preparation_steps_never_apply_the_reference_repair():
    for case in discover_cases():
        if case.upstream is None:
            continue
        for step in case.upstream.preparation_steps:
            argv_str = " ".join(step.argv)
            assert "fix.patch" not in argv_str
            assert "git apply" not in argv_str
            assert "reference" not in argv_str


def test_prepared_real_case_repo_has_no_git_directory():
    """No reachable future (post-fix) history must be locally retrievable
    from the reconstruction cache a staged copy is made from."""
    for case in discover_cases():
        if case.upstream is None or not is_prepared(case):
            continue
        assert not (repo_dir(case) / ".git").exists()


def test_prepared_real_case_repo_is_checked_out_at_the_buggy_commit():
    for case in discover_cases():
        if case.upstream is None or not is_prepared(case):
            continue
        # No .git directory means we can't ask git; instead confirm the
        # working tree matches the buggy (not fixed) production file: the
        # reference-repair patch must still apply cleanly from this state.
        proc = subprocess.run(
            [
                "git",
                "apply",
                "--check",
                str((DEFAULT_BENCHMARK_ROOT / case.path / case.reference_repair.patch).resolve()),
            ],
            cwd=repo_dir(case),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, (
            f"{case.id}: reference-repair patch does not apply cleanly to the prepared "
            f"checkout -- it may not be at the pinned buggy commit. stderr: {proc.stderr}"
        )
