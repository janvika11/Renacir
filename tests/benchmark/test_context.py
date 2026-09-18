import json

from renacir.benchmark.context import ModelFacingContext, build_model_facing_context
from renacir.benchmark.discovery import (
    DEFAULT_BENCHMARK_ROOT,
    DEFAULT_MANIFEST_PATH,
    discover_cases,
)
from renacir.benchmark.models import (
    ContaminationRisk,
    CurationMetadata,
    IndependentCheck,
    ReferenceRepair,
    SourceMetadata,
)

TIER_C_AND_D_FIELD_NAMES = (
    set(CurationMetadata.model_fields)
    | set(SourceMetadata.model_fields)
    | set(ContaminationRisk.model_fields)
    | set(ReferenceRepair.model_fields)
    | set(IndependentCheck.model_fields)
)


def test_model_facing_context_has_no_tier_c_or_d_fields():
    assert set(ModelFacingContext.model_fields).isdisjoint(TIER_C_AND_D_FIELD_NAMES)


def test_build_model_facing_context_does_not_touch_reference_repair_or_curation():
    for case in discover_cases():
        context = build_model_facing_context(case)

        assert not hasattr(context, "reference_repair")
        assert not hasattr(context, "curation")
        assert not hasattr(context, "source")
        assert not hasattr(context, "independent_checks")


def test_independent_check_paths_never_appear_in_model_facing_context():
    for case in discover_cases():
        context = build_model_facing_context(case)
        serialized = json.dumps(context.model_dump())

        for check in case.independent_checks:
            assert check.path not in serialized
            assert check.description not in serialized


def test_staged_case_never_contains_reference_directory():
    from renacir.benchmark.runner import staged_case

    for case in discover_cases():
        with staged_case(case, DEFAULT_BENCHMARK_ROOT) as staged:
            assert not (staged / "reference").exists(), (
                f"{case.id}: reference/ (Tier D) must not be present in the staged, "
                "model-visible directory tree"
            )


def test_model_facing_context_serialization_excludes_forbidden_keys():
    forbidden_substrings = ("patch", "dedup", "contamination", "rejection", "source_group")

    for case in discover_cases():
        context = build_model_facing_context(case)
        serialized = json.dumps(context.model_dump())

        for forbidden in forbidden_substrings:
            assert forbidden not in serialized.lower(), (
                f"Tier B context for {case.id} unexpectedly contains {forbidden!r}"
            )


def test_reference_repair_patch_paths_are_never_referenced_in_manifest_execution_fields():
    raw = json.loads(DEFAULT_MANIFEST_PATH.read_text())
    for case in raw["cases"]:
        patch_path = case["reference_repair"]["patch"]
        assert patch_path not in case["command"]
        assert patch_path != case["failing_test"]
