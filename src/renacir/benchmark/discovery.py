import json
from pathlib import Path

from renacir.benchmark.models import BenchmarkCase, BenchmarkManifest

DEFAULT_BENCHMARK_ROOT = Path(__file__).resolve().parents[3] / "benchmarks"
DEFAULT_MANIFEST_PATH = DEFAULT_BENCHMARK_ROOT / "manifest.json"

SUPPORTED_SCHEMA_VERSION = 2


def load_manifest(manifest_path: Path = DEFAULT_MANIFEST_PATH) -> BenchmarkManifest:
    data = json.loads(manifest_path.read_text())
    manifest = BenchmarkManifest.model_validate(data)
    if manifest.schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported manifest schema_version {manifest.schema_version} "
            f"(expected {SUPPORTED_SCHEMA_VERSION}): {manifest_path}"
        )
    return manifest


def discover_cases(manifest_path: Path = DEFAULT_MANIFEST_PATH) -> list[BenchmarkCase]:
    return load_manifest(manifest_path).cases


def case_dir(case: BenchmarkCase, benchmark_root: Path = DEFAULT_BENCHMARK_ROOT) -> Path:
    return benchmark_root / case.path


def validate_case_paths(case: BenchmarkCase, benchmark_root: Path = DEFAULT_BENCHMARK_ROOT) -> None:
    directory = case_dir(case, benchmark_root)
    if not directory.is_dir():
        raise FileNotFoundError(f"{case.id}: case directory not found: {directory}")

    patch_path = directory / case.reference_repair.patch
    if not patch_path.is_file():
        raise FileNotFoundError(f"{case.id}: reference repair patch not found: {patch_path}")

    test_file = case.failing_test.split("::", 1)[0]
    if not (directory / test_file).is_file():
        raise FileNotFoundError(f"{case.id}: failing test file not found: {directory / test_file}")
