"""Candidate curation records — accepted and rejected real-world benchmark
candidates, kept separate from the executable manifest (`manifest.json`).

A rejected candidate is not, and is never required to become, an executable
`BenchmarkCase` — it has no path, command, or reference repair. This module
exists to make rejections traceable rather than silently dropped, per
`docs/research_protocol.md` §6's "reviewed and rejected" principle, applied
to real-case sourcing.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from renacir.benchmark.models import SourceType

DEFAULT_CANDIDATES_PATH = Path(__file__).resolve().parents[3] / "benchmarks" / "candidates.json"

CANDIDATES_SCHEMA_VERSION = 1


class CandidateCurationRecord(BaseModel):
    candidate_id: str
    source: SourceType
    upstream_identifier: str | None = None
    review_date: str
    decision: Literal["accepted", "rejected"]
    rejection_reasons: list[str] = []
    license_notes: str | None = None
    reproducibility_notes: str | None = None
    benchmark_case_id: str | None = None


class CandidateCurationLog(BaseModel):
    schema_version: int
    records: list[CandidateCurationRecord]


def load_candidate_log(path: Path = DEFAULT_CANDIDATES_PATH) -> CandidateCurationLog:
    data = json.loads(path.read_text())
    log = CandidateCurationLog.model_validate(data)
    if log.schema_version != CANDIDATES_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported candidate log schema_version {log.schema_version} "
            f"(expected {CANDIDATES_SCHEMA_VERSION}): {path}"
        )
    return log
