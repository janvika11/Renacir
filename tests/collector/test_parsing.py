"""Failure-parsing tests. Uses real captured pytest output (via the actual
benchmark runner against real fixtures) rather than hand-fabricated strings,
so parsing is verified against what pytest genuinely produces, not a guess
at its format.
"""

from renacir.benchmark.discovery import discover_cases
from renacir.benchmark.runner import run_tests, staged_case
from renacir.collector.collector import _purge_stale_caches
from renacir.collector.parsing import parse_failure


def _run_and_parse(case_id):
    case = next(c for c in discover_cases() if c.id == case_id)
    with staged_case(case) as staged:
        _purge_stale_caches(staged)  # mirror collector.collect()'s real usage
        result = run_tests(case, staged)
        return parse_failure(result.stdout, staged), result


def test_assertion_failure_is_parsed():
    parsed, result = _run_and_parse("assertion-average-off-by-one")

    assert result.returncode != 0
    assert parsed.error_type == "AssertionError"
    assert parsed.error_message is not None
    assert "assert" in parsed.error_message
    assert parsed.summary is not None
    assert "FAILED" in parsed.summary
    assert any(frame.file == "test_stats.py" for frame in parsed.frames)


def test_import_failure_is_parsed():
    parsed, result = _run_and_parse("import-renamed-helper")

    assert result.returncode != 0
    assert parsed.error_type == "ImportError"
    assert parsed.error_message is not None
    assert "helper" in parsed.error_message
    assert {frame.file for frame in parsed.frames} >= {"test_main.py", "main.py"}


def test_all_synthetic_cases_produce_some_parsed_signal():
    """Every synthetic case's genuine failure output yields at least an
    error_type or a summary — parsing isn't accidentally a no-op across the
    whole fixture set."""
    for case in discover_cases():
        if case.upstream is not None:
            continue
        with staged_case(case) as staged:
            _purge_stale_caches(staged)
            result = run_tests(case, staged)
        parsed = parse_failure(result.stdout, staged)
        assert parsed.error_type is not None or parsed.summary is not None, case.id


def test_malformed_output_yields_unavailable_not_guessed(tmp_path):
    parsed = parse_failure("completely unstructured text with no pytest markers\n", tmp_path)

    assert parsed.error_type is None
    assert parsed.frames == []


def test_empty_output_yields_unavailable(tmp_path):
    parsed = parse_failure("", tmp_path)

    assert parsed.error_type is None
    assert parsed.error_message is None
    assert parsed.frames == []
    assert parsed.summary is None


def test_frame_paths_outside_case_root_are_excluded(tmp_path):
    stdout = (
        "/some/other/place/lib.py:10: in call\n"
        "    do_something()\n"
        f"{tmp_path.resolve()}/inside.py:5: ValueError\n"
    )
    (tmp_path / "inside.py").write_text("x = 1\n")

    parsed = parse_failure(stdout, tmp_path)

    files = {frame.file for frame in parsed.frames}
    assert "inside.py" in files
    assert not any("/some/other/place" in f for f in files)


def test_venv_and_site_packages_frames_are_excluded(tmp_path):
    venv_frame = f"{tmp_path.resolve()}/venv/lib/python3.11/site-packages/pluggy/_callers.py"
    stdout = f"{venv_frame}:167: in _multicall\n{tmp_path.resolve()}/app.py:3: RuntimeError\n"
    (tmp_path / "app.py").write_text("x = 1\n")

    parsed = parse_failure(stdout, tmp_path)

    files = {frame.file for frame in parsed.frames}
    assert files == {"app.py"}
