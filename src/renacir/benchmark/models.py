from typing import Literal

from pydantic import BaseModel

FailureCategory = Literal["assertion", "import"]


class ExpectedRepair(BaseModel):
    patch: str


class BenchmarkCase(BaseModel):
    id: str
    category: FailureCategory
    path: str
    command: list[str]
    failing_test: str
    expected_repair: ExpectedRepair


class BenchmarkManifest(BaseModel):
    schema_version: int
    cases: list[BenchmarkCase]
