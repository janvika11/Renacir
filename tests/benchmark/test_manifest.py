import json

import pytest
from pydantic import ValidationError

from renacir.benchmark.discovery import (
    DEFAULT_BENCHMARK_ROOT,
    DEFAULT_MANIFEST_PATH,
    SUPPORTED_SCHEMA_VERSION,
    discover_cases,
    load_manifest,
    validate_case_paths,
)
from renacir.benchmark.models import BenchmarkManifest

ALL_CASE_IDS = {
    "assertion-average-off-by-one",
    "import-renamed-helper",
    "assertion-discount-boolean-logic",
    "assertion-tags-mutable-default",
    "assertion-truncate-empty-edge-case",
    "assertion-config-fallback-default",
    "import-reportpkg-missing-reexport",
    "import-reportpkg-bad-local-import",
    "import-reportpkg-broken-init",
    "httpie-none-header-skip",
    "httpie-custom-host-header",
    "click-path-resolve-symlink",
}


def test_discover_cases_returns_all_phase_2b_cases():
    cases = discover_cases()
    ids = {case.id for case in cases}

    assert ids == ALL_CASE_IDS


def test_case_ids_are_unique():
    cases = discover_cases()
    ids = [case.id for case in cases]

    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("case", discover_cases(), ids=lambda case: case.id)
def test_case_category_is_known(case):
    assert case.category in {"assertion", "import"}


@pytest.mark.parametrize("case", discover_cases(), ids=lambda case: case.id)
def test_case_referenced_paths_exist_on_disk(case):
    validate_case_paths(case, DEFAULT_BENCHMARK_ROOT)


@pytest.mark.parametrize("case", discover_cases(), ids=lambda case: case.id)
def test_case_reference_repair_loads(case):
    assert case.reference_repair.patch == "reference/fix.patch"


@pytest.mark.parametrize("case", discover_cases(), ids=lambda case: case.id)
def test_case_source_group_id_is_nonempty(case):
    assert case.source.source_group_id.strip() != ""


@pytest.mark.parametrize("case", discover_cases(), ids=lambda case: case.id)
def test_case_has_reproducibility_check_version(case):
    assert case.execution.reproducibility_check_version.strip() != ""


def test_real_manifest_loads_at_current_schema_version():
    manifest = load_manifest()
    assert manifest.schema_version == SUPPORTED_SCHEMA_VERSION == 2


def test_two_original_fixtures_have_distinct_source_groups():
    cases = {case.id: case for case in discover_cases()}
    assert (
        cases["assertion-average-off-by-one"].source.source_group_id
        != cases["import-renamed-helper"].source.source_group_id
    )


def test_reportpkg_cases_share_a_source_group():
    cases = {case.id: case for case in discover_cases()}
    reportpkg_ids = [
        "import-reportpkg-missing-reexport",
        "import-reportpkg-bad-local-import",
        "import-reportpkg-broken-init",
    ]
    groups = {cases[cid].source.source_group_id for cid in reportpkg_ids}
    assert groups == {"synthetic:reportpkg-template"}


def test_textstats_cases_share_a_source_group():
    cases = {case.id: case for case in discover_cases()}
    groups = {
        cases["assertion-tags-mutable-default"].source.source_group_id,
        cases["assertion-truncate-empty-edge-case"].source.source_group_id,
    }
    assert groups == {"synthetic:textstats-template"}


def test_source_groups_are_not_all_singletons():
    cases = discover_cases()
    group_counts: dict[str, int] = {}
    for case in cases:
        group_counts[case.source.source_group_id] = (
            group_counts.get(case.source.source_group_id, 0) + 1
        )

    assert any(count > 1 for count in group_counts.values()), (
        "expected at least one source group with more than one case; "
        "grouping must not default to a unique group per case"
    )


@pytest.mark.parametrize(
    "case",
    [c for c in discover_cases() if c.independent_checks],
    ids=lambda case: case.id,
)
def test_independent_check_files_exist_on_disk(case):
    directory = DEFAULT_BENCHMARK_ROOT / case.path
    for check in case.independent_checks:
        assert (directory / check.path).is_file()


def test_dropped_candidate_is_not_in_the_executable_manifest():
    ids = {case.id for case in discover_cases()}
    assert "assertion-tax-wrong-constant" not in ids


def test_manifest_rejects_unsupported_schema_version(tmp_path):
    bad_manifest = json.loads(DEFAULT_MANIFEST_PATH.read_text())
    bad_manifest["schema_version"] = 999
    bad_path = tmp_path / "manifest.json"
    bad_path.write_text(json.dumps(bad_manifest))

    with pytest.raises(ValueError, match="unsupported manifest schema_version"):
        load_manifest(bad_path)


def test_manifest_rejects_missing_reference_repair():
    raw = json.loads(DEFAULT_MANIFEST_PATH.read_text())
    del raw["cases"][0]["reference_repair"]

    with pytest.raises(ValidationError):
        BenchmarkManifest.model_validate(raw)


def test_manifest_rejects_invalid_source_type():
    raw = json.loads(DEFAULT_MANIFEST_PATH.read_text())
    raw["cases"][0]["source"]["type"] = "fabricated"

    with pytest.raises(ValidationError):
        BenchmarkManifest.model_validate(raw)


def test_manifest_rejects_missing_reproducibility_check_version():
    raw = json.loads(DEFAULT_MANIFEST_PATH.read_text())
    del raw["cases"][0]["execution"]["reproducibility_check_version"]

    with pytest.raises(ValidationError):
        BenchmarkManifest.model_validate(raw)


def test_manifest_rejects_invalid_curation_status():
    raw = json.loads(DEFAULT_MANIFEST_PATH.read_text())
    raw["cases"][0]["curation"]["status"] = "maybe"

    with pytest.raises(ValidationError):
        BenchmarkManifest.model_validate(raw)


REAL_CASE_IDS = {
    "httpie-none-header-skip",
    "httpie-custom-host-header",
    "click-path-resolve-symlink",
}


@pytest.mark.parametrize(
    "case", [c for c in discover_cases() if c.id not in REAL_CASE_IDS], ids=lambda case: case.id
)
def test_synthetic_cases_have_no_upstream_provenance(case):
    assert case.upstream is None
    assert case.test_overlay is None


@pytest.mark.parametrize(
    "case", [c for c in discover_cases() if c.id in REAL_CASE_IDS], ids=lambda case: case.id
)
def test_real_cases_have_upstream_provenance(case):
    assert case.upstream is not None
    assert case.upstream.real_ci_subtype == "real_ci_c"
    assert case.upstream.historical_runtime is not None
    assert case.upstream.reconstruction_runtime.python_version
    assert case.upstream.preparation_steps
    assert case.upstream.preparation_requires_network is True
    assert case.upstream.evaluation_requires_network is False


def test_manifest_rejects_invalid_real_ci_subtype():
    raw = json.loads(DEFAULT_MANIFEST_PATH.read_text())
    real_case = next(c for c in raw["cases"] if c["id"] == "click-path-resolve-symlink")
    real_case["upstream"]["real_ci_subtype"] = "real_ci_z"

    with pytest.raises(ValidationError):
        BenchmarkManifest.model_validate(raw)


def test_manifest_rejects_real_case_missing_buggy_commit():
    raw = json.loads(DEFAULT_MANIFEST_PATH.read_text())
    real_case = next(c for c in raw["cases"] if c["id"] == "click-path-resolve-symlink")
    del real_case["upstream"]["buggy_commit"]

    with pytest.raises(ValidationError):
        BenchmarkManifest.model_validate(raw)


def test_manifest_accepts_case_with_no_upstream_key_at_all():
    raw = json.loads(DEFAULT_MANIFEST_PATH.read_text())
    synthetic_case = next(c for c in raw["cases"] if c["id"] not in REAL_CASE_IDS)
    assert "upstream" not in synthetic_case or synthetic_case["upstream"] is None


def test_unrestricted_pytest_still_cannot_collect_benchmark_or_cache_files():
    """`benchmarks/` (fixtures, patches, evaluator-only checks) and
    `.benchmark-cache/` (real cases' reconstructed checkouts, which carry
    their own upstream pytest configs/tests) must never be swept into a bare
    `pytest` collection run from the repository root — see `testpaths` and
    `addopts` in pyproject.toml.
    """
    import subprocess

    repo_root = DEFAULT_BENCHMARK_ROOT.parent
    proc = subprocess.run(
        ["pytest", "--collect-only", "-q"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "benchmarks/" not in proc.stdout
    assert ".benchmark-cache" not in proc.stdout
