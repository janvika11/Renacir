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


def test_discover_cases_returns_both_seed_cases():
    cases = discover_cases()
    ids = {case.id for case in cases}

    assert ids == {"assertion-average-off-by-one", "import-renamed-helper"}


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


def test_two_current_fixtures_have_distinct_source_groups():
    cases = {case.id: case for case in discover_cases()}
    assert (
        cases["assertion-average-off-by-one"].source.source_group_id
        != cases["import-renamed-helper"].source.source_group_id
    )


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
