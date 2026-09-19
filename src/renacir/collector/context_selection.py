"""Deterministic, bounded source-context selection.

Priority order:
1. Files referenced by the parsed traceback — what the interpreter actually
   executed, the strongest evidence of relevance.
2. The failing test file itself — **only** when it's an original fixture
   (`case.test_overlay is None`). For a reconstructed real case, this rule
   is skipped entirely.
3. Local imports of the failing test file (a narrow, static, one-level
   heuristic — no transitive resolution) — likewise only for an original
   fixture, and a deliberate supplement for import-category failures, whose
   traceback is often too shallow (just the import statement site) to
   surface the actually-relevant module on its own.

**The retrospective test overlay's own file is categorically excluded from
ever becoming a `SelectedFile`**, regardless of which rule would otherwise
select it — even if `frame.file == case.test_overlay.target_path` appears in
the traceback (rule 1). This is the Phase 3 Collector's approved
information-boundary decision: a retrospective overlay may be executed to
reconstruct a historical failure, and its file/line may appear in
`ParsedFailure.frames` (traceback information is explicitly allowed), but
its source text must never appear anywhere in `CollectorOutput`. Treat it as
evaluator-only reconstruction infrastructure — see `docs/collector.md`.
"""

import ast
from pathlib import Path

from renacir.benchmark.models import BenchmarkCase
from renacir.collector.models import ContextSelectionLimits, ParsedFailure, SelectedFile


def _withheld_path(case: BenchmarkCase) -> str | None:
    if case.test_overlay is None:
        return None
    return case.test_overlay.target_path


def _read_truncated(path: Path, limits: ContextSelectionLimits) -> tuple[str, bool]:
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    truncated = False
    if len(lines) > limits.max_lines_per_file:
        lines = lines[: limits.max_lines_per_file]
        truncated = True
    content = "\n".join(lines)
    if len(content) > limits.max_chars_per_file:
        content = content[: limits.max_chars_per_file]
        truncated = True
    return content, truncated


def _local_imports(test_path: Path, staged_root: Path) -> list[str]:
    try:
        tree = ast.parse(test_path.read_text(errors="replace"))
    except SyntaxError:
        return []

    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)

    resolved: list[str] = []
    for module in modules:
        candidate = staged_root / (module.replace(".", "/") + ".py")
        if candidate.is_file():
            resolved.append(str(candidate.relative_to(staged_root)))
    return resolved


def select_context(
    staged_root: Path,
    case: BenchmarkCase,
    parsed: ParsedFailure,
    limits: ContextSelectionLimits,
) -> list[SelectedFile]:
    withheld = _withheld_path(case)
    selected: list[SelectedFile] = []
    seen: set[str] = set()
    total_chars = 0

    def try_add(rel_path: str, reason: str) -> None:
        nonlocal total_chars
        if rel_path == withheld:
            return
        if rel_path in seen or len(selected) >= limits.max_files:
            return
        full = staged_root / rel_path
        if not full.is_file():
            return
        content, truncated = _read_truncated(full, limits)
        if total_chars + len(content) > limits.max_total_context_chars:
            remaining = limits.max_total_context_chars - total_chars
            if remaining <= 0:
                return
            content = content[:remaining]
            truncated = True
        selected.append(
            SelectedFile(path=rel_path, content=content, truncated=truncated, reason=reason)
        )
        seen.add(rel_path)
        total_chars += len(content)

    for frame in parsed.frames:
        try_add(frame.file, "traceback_reference")

    if withheld is None:
        test_file = case.failing_test.split("::", 1)[0]
        try_add(test_file, "failing_test")

        test_path = staged_root / test_file
        if test_path.is_file():
            for local_module in _local_imports(test_path, staged_root):
                try_add(local_module, "local_import")

    return selected
