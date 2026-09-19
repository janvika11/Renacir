import pytest
from pydantic import ValidationError

from renacir.diagnoser.models import DiagnoserInput, Diagnosis


def test_diagnoser_input_has_no_category_field():
    assert "category" not in DiagnoserInput.model_fields


def test_diagnoser_input_has_no_evaluator_only_fields():
    forbidden = {
        "reference_repair",
        "independent_checks",
        "curation",
        "upstream",
        "test_overlay",
        "source",
        "failing_test_provenance",
    }
    assert forbidden.isdisjoint(set(DiagnoserInput.model_fields))


def _valid_diagnosis_kwargs(**overrides):
    kwargs = dict(
        root_cause_summary="x",
        suspected_files=[],
        suspected_symbols=[],
        reasoning_summary="y",
        diagnosis_confidence=0.5,
        insufficient_context=False,
    )
    kwargs.update(overrides)
    return kwargs


def test_diagnosis_confidence_must_be_in_bounds():
    Diagnosis(**_valid_diagnosis_kwargs(diagnosis_confidence=0.0))
    Diagnosis(**_valid_diagnosis_kwargs(diagnosis_confidence=1.0))
    with pytest.raises(ValidationError):
        Diagnosis(**_valid_diagnosis_kwargs(diagnosis_confidence=1.5))
    with pytest.raises(ValidationError):
        Diagnosis(**_valid_diagnosis_kwargs(diagnosis_confidence=-0.1))


def test_diagnosis_root_cause_summary_length_bounded():
    with pytest.raises(ValidationError):
        Diagnosis(**_valid_diagnosis_kwargs(root_cause_summary="x" * 3000))


def test_diagnosis_reasoning_summary_length_bounded():
    with pytest.raises(ValidationError):
        Diagnosis(**_valid_diagnosis_kwargs(reasoning_summary="x" * 5000))


def test_diagnosis_suspected_files_list_bounded():
    with pytest.raises(ValidationError):
        Diagnosis(**_valid_diagnosis_kwargs(suspected_files=[f"f{i}.py" for i in range(25)]))


def test_diagnosis_suspected_symbols_list_bounded():
    with pytest.raises(ValidationError):
        Diagnosis(**_valid_diagnosis_kwargs(suspected_symbols=[f"s{i}" for i in range(25)]))


def test_diagnosis_suspected_file_path_length_bounded():
    with pytest.raises(ValidationError):
        Diagnosis(**_valid_diagnosis_kwargs(suspected_files=["x" * 1000]))


def test_diagnosis_suspected_symbol_length_bounded():
    with pytest.raises(ValidationError):
        Diagnosis(**_valid_diagnosis_kwargs(suspected_symbols=["x" * 1000]))


def test_insufficient_context_does_not_require_populated_lists():
    diagnosis = Diagnosis(
        **_valid_diagnosis_kwargs(
            insufficient_context=True,
            suspected_files=[],
            suspected_symbols=[],
            diagnosis_confidence=0.1,
        )
    )
    assert diagnosis.insufficient_context is True
    assert diagnosis.suspected_files == []
    assert diagnosis.suspected_symbols == []


def test_diagnosis_schema_has_no_patch_or_diff_field():
    forbidden_field_names = {"patch", "diff", "fix", "repair", "code_change", "replacement_code"}
    assert forbidden_field_names.isdisjoint(set(Diagnosis.model_fields))
