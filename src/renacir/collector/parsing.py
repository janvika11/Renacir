"""Deterministic, LLM-free failure parsing.

Parses pytest's own textual failure report (captured stdout) with regular
expressions — never an LLM, never a guess. Any field that can't be
determined with confidence is left `None`/empty; raw stdout/stderr on
`CollectorOutput` always preserve the full underlying evidence regardless of
what this module manages to extract.

Handles two pytest report shapes, both observed against this project's own
fixtures: the default multi-line report (a `File:line:` style location
trailer plus `E   ` detail lines) and the condensed `--tb=line` report (one
`file:line: ExceptionType: message` line per failure, used by
`renacir.collector.collector` for reconstructed real cases specifically to
avoid echoing retrospective test-overlay source through pytest's normal
source-context rendering).
"""

import re
from pathlib import Path

from renacir.collector.models import ParsedFailure, TracebackFrame

_LOCATION_TRAILER = re.compile(
    r"^(?P<file>\S+\.py):(?P<line>\d+): (?:in (?P<func>\S+)|(?P<exc>\w+))?\s*$"
)
_TB_LINE_FAILURE = re.compile(r"^(?P<file>\S+\.py):(?P<line>\d+): (?P<exc>[\w.]+): ?(?P<msg>.*)$")
_FAILED_SUMMARY = re.compile(r"^FAILED (?P<nodeid>\S+)(?: - (?P<msg>.*))?$")
_ERROR_DETAIL = re.compile(r"^E\s+(?P<rest>.*)$")
_ERROR_TYPE_AND_MESSAGE = re.compile(
    r"^(?P<type>[A-Za-z_][\w.]*(?:Error|Exception|Warning))\b(?::\s*(?P<msg>.*))?$"
)

_EXCLUDED_PATH_SEGMENTS = (
    "venv",
    "site-packages",
    ".benchmark-cache",
    "__pycache__",
    ".pytest_cache",
)


def _normalize_frame_path(raw_path: str, staged_root: Path) -> str | None:
    """Return `raw_path` as a clean, forward-slash path relative to
    `staged_root`, or `None` if it must be excluded entirely (points outside
    the staged case root, or into venv/dependency/cache internals — this is
    what keeps a real case's local `.benchmark-cache/<id>/venv/...` layout,
    and any absolute host path generally, out of every `TracebackFrame`).

    Operates on the RAW (unredacted) path, via `Path.relative_to`, rather
    than lexical string matching against a placeholder — a prior
    implementation redacted absolute paths to a `<case-root>` placeholder
    *before* parsing, which silently corrupted every frame path into an
    unresolvable literal and emptied context selection. Text-level
    redaction of `stdout`/`stderr` for display happens separately, in
    `renacir.collector.collector`, using the ORIGINAL text for parsing.
    """
    candidate = Path(raw_path)
    if candidate.is_absolute():
        try:
            relative = candidate.resolve().relative_to(staged_root.resolve())
        except ValueError:
            return None
    else:
        normalized = raw_path.replace("\\", "/")
        if ".." in normalized.split("/"):
            return None
        relative = Path(normalized)

    parts = relative.parts
    if any(segment in _EXCLUDED_PATH_SEGMENTS for segment in parts):
        return None
    return relative.as_posix()


def parse_failure(stdout: str, staged_root: Path) -> ParsedFailure:
    lines = stdout.splitlines()

    # `--tb=line` reports: exactly one location+type+message line per failure.
    tb_line_matches = [m for line in lines if (m := _TB_LINE_FAILURE.match(line))]

    error_type: str | None = None
    error_message: str | None = None
    frames: list[TracebackFrame] = []

    if tb_line_matches:
        first = tb_line_matches[0]
        error_type = first.group("exc")
        error_message = first.group("msg") or None
        for m in tb_line_matches:
            normalized = _normalize_frame_path(m.group("file"), staged_root)
            if normalized is not None:
                frames.append(
                    TracebackFrame(file=normalized, line=int(m.group("line")), function=None)
                )
    else:
        error_detail_lines = [m.group("rest") for line in lines if (m := _ERROR_DETAIL.match(line))]
        if error_detail_lines:
            first_detail = error_detail_lines[0]
            type_match = _ERROR_TYPE_AND_MESSAGE.match(first_detail)
            if type_match:
                error_type = type_match.group("type")
                error_message = type_match.group("msg") or None
                if not error_message and len(error_detail_lines) > 1:
                    error_message = error_detail_lines[1]
            else:
                error_message = first_detail

        for line in lines:
            m = _LOCATION_TRAILER.match(line)
            if not m:
                continue
            # The exception type on a trailer line is legitimate signal
            # regardless of whether its file path normalizes to something
            # inside the case root (e.g. a frame in a dependency, or —
            # observed during implementation — a stale absolute path baked
            # into leftover `.pyc` bytecode from an earlier direct `pytest`
            # run in the fixture directory); only the FRAME itself is
            # withheld when the path can't be normalized, never the type.
            exc = m.group("exc")
            if error_type is None and exc:
                error_type = exc
            normalized = _normalize_frame_path(m.group("file"), staged_root)
            if normalized is None:
                continue
            frames.append(
                TracebackFrame(file=normalized, line=int(m.group("line")), function=m.group("func"))
            )

    summary: str | None = None
    for line in lines:
        m = _FAILED_SUMMARY.match(line)
        if m:
            summary = line.strip()
            break
    if summary is None and error_type:
        summary = f"{error_type}: {error_message}" if error_message else error_type

    return ParsedFailure(
        error_type=error_type,
        error_message=error_message,
        frames=frames,
        summary=summary,
    )
