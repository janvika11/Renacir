"""Automated diagnosis-evaluation helpers — evaluator-only, computed
strictly after a `DiagnosisRunRecord` already exists. Nothing here feeds
back into `renacir.diagnoser`; nothing in `renacir.diagnoser` imports this
module.

Reuses `renacir.evaluation.retrieval.reference_relevant_files` for "what did
the historical repair touch" rather than defining a second reference set.

Only the automatable signals approved in the Phase 4A design are
implemented here: suspected-file precision/recall/F1, grounding-violation
rate, parse-success rate, insufficient-context rate, and latency/token
summaries. Semantic root-cause correctness is **not** implemented as
automation — see `docs/diagnoser.md`'s blinded human rubric, deliberately
left as a documented, separate, later manual step rather than faked here.
"""

from pydantic import BaseModel

from renacir.benchmark.models import BenchmarkCase
from renacir.diagnoser.models import DiagnosisRunRecord
from renacir.evaluation.retrieval import reference_relevant_files


class SuspectedFileScore(BaseModel):
    """`None` fields mean "not computable for this record," never a
    fabricated 0 — mirrors `RetrievalDiagnostic`'s own None-over-invented-zero
    convention.
    """

    precision: float | None
    recall: float | None
    f1: float | None
    reference_files_available: bool


def score_suspected_files(record: DiagnosisRunRecord, case: BenchmarkCase) -> SuspectedFileScore:
    reference_files = reference_relevant_files(case)
    if reference_files is None or record.parsed_diagnosis is None:
        return SuspectedFileScore(
            precision=None,
            recall=None,
            f1=None,
            reference_files_available=reference_files is not None,
        )

    suspected = set(record.parsed_diagnosis.suspected_files)
    reference = set(reference_files)

    precision = (len(suspected & reference) / len(suspected)) if suspected else 0.0
    recall = len(suspected & reference) / len(reference)
    f1 = None
    if (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)

    return SuspectedFileScore(
        precision=precision, recall=recall, f1=f1, reference_files_available=True
    )


def parse_success_rate(records: list[DiagnosisRunRecord]) -> float | None:
    if not records:
        return None
    return sum(1 for r in records if r.parse_status == "ok") / len(records)


def insufficient_context_rate(records: list[DiagnosisRunRecord]) -> float | None:
    parsed = [r for r in records if r.parsed_diagnosis is not None]
    if not parsed:
        return None
    return sum(1 for r in parsed if r.parsed_diagnosis.insufficient_context) / len(parsed)


def grounding_violation_rate(records: list[DiagnosisRunRecord]) -> float | None:
    parsed = [r for r in records if r.parsed_diagnosis is not None]
    if not parsed:
        return None
    return sum(1 for r in parsed if r.grounding_violation) / len(parsed)


class LatencyTokenSummary(BaseModel):
    count: int
    mean_latency_seconds: float | None
    mean_input_tokens: float | None
    mean_output_tokens: float | None


def summarize_latency_and_tokens(records: list[DiagnosisRunRecord]) -> LatencyTokenSummary:
    latencies = [r.latency_seconds for r in records if r.latency_seconds is not None]
    input_tokens = [r.input_tokens for r in records if r.input_tokens is not None]
    output_tokens = [r.output_tokens for r in records if r.output_tokens is not None]
    return LatencyTokenSummary(
        count=len(records),
        mean_latency_seconds=(sum(latencies) / len(latencies)) if latencies else None,
        mean_input_tokens=(sum(input_tokens) / len(input_tokens)) if input_tokens else None,
        mean_output_tokens=(sum(output_tokens) / len(output_tokens)) if output_tokens else None,
    )
