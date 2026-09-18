from renacir.benchmark.curation import (
    CANDIDATES_SCHEMA_VERSION,
    DEFAULT_CANDIDATES_PATH,
    CandidateCurationLog,
    CandidateCurationRecord,
    load_candidate_log,
)


def test_candidate_log_loads_at_current_schema_version():
    log = load_candidate_log()
    assert log.schema_version == CANDIDATES_SCHEMA_VERSION


def test_candidate_log_records_the_phase_2b_dropped_candidate():
    log = load_candidate_log()
    record = next(r for r in log.records if r.candidate_id == "assertion-tax-wrong-constant")

    assert record.decision == "rejected"
    assert record.benchmark_case_id is None
    assert record.rejection_reasons != []


def test_no_real_world_candidates_recorded_yet():
    log = load_candidate_log()
    assert all(r.source != "real" for r in log.records)


def test_candidates_file_exists_and_is_separate_from_manifest():
    assert DEFAULT_CANDIDATES_PATH.name == "candidates.json"
    assert DEFAULT_CANDIDATES_PATH.exists()


def test_rejected_candidate_can_be_represented_without_being_executable():
    record = CandidateCurationRecord(
        candidate_id="candidate-example-001",
        source="real",
        upstream_identifier="https://example.invalid/some/repo@deadbeef",
        review_date="2026-09-18",
        decision="rejected",
        rejection_reasons=["architecture-wide refactor required", "license unclear"],
        license_notes="repository has no LICENSE file",
    )

    assert record.decision == "rejected"
    assert record.benchmark_case_id is None
    assert not hasattr(record, "path")
    assert not hasattr(record, "command")
    assert not hasattr(record, "reference_repair")


def test_accepted_candidate_may_point_at_a_benchmark_case_id():
    record = CandidateCurationRecord(
        candidate_id="candidate-example-002",
        source="synthetic",
        review_date="2026-09-18",
        decision="accepted",
        benchmark_case_id="assertion-average-off-by-one",
    )

    assert record.benchmark_case_id == "assertion-average-off-by-one"


def test_candidate_log_round_trips_through_the_model():
    log = CandidateCurationLog(
        schema_version=CANDIDATES_SCHEMA_VERSION,
        records=[
            CandidateCurationRecord(
                candidate_id="candidate-example-003",
                source="real",
                review_date="2026-09-18",
                decision="rejected",
                rejection_reasons=["flaky"],
            )
        ],
    )

    assert len(log.records) == 1
    assert log.records[0].decision == "rejected"
