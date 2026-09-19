# Collector

**Status: Phase 3, 2026-09-19.** The first implemented pipeline component (`src/renacir/collector/`).
Collects evidence only — it does not diagnose, does not suggest a fix, does not generate a
patch, does not call an LLM, and never makes a confidence decision. It is the first stage of
the pipeline described in `ARCHITECTURE.md`.

**Scope**: this phase's Collector consumes benchmark cases (synthetic fixtures and
reconstructed real-world REAL-CI-C cases) via the existing `renacir.benchmark`
staging/execution infrastructure. It does not ingest a live GitHub Actions run — that's a
later integration phase. `ARCHITECTURE.md`'s data-flow diagram ("Failed CI run → Collector")
describes the eventual system; today, "Failed CI run" is operationalized as "a benchmark case,
staged and executed locally or via a reconstruction recipe."

## Contract

`CollectorInput(case_id, limits=ContextSelectionLimits())` → `CollectorOutput`.

`CollectorOutput` embeds `renacir.benchmark.context.ModelFacingContext` (`context` field) —
the existing Tier-B allowlist — rather than re-deriving `failing_test`/`command`/`category`,
plus:

- `failing_test_provenance`: `"original_fixture"` or `"reconstructed_retrospective_overlay"` —
  see "Retrospective test overlays" below.
- `exit_code`, `stdout`, `stderr` — the actual observed execution result, truncated per
  `limits_applied`, with local host paths redacted to stable placeholders (`<case-root>`,
  `<reconstruction-cache>`, `<tmp>` — see "Determinism and path redaction" below).
- `parsed_failure`: `ParsedFailure` — deterministically parsed, never guessed.
- `selected_context`: `list[SelectedFile]` — deterministic, bounded (see below).
- `repository_structure`: a bounded filename listing (no content), cache/VCS directories
  excluded.
- `runtime`: the Python version actually observed running the failing test this run — never
  `upstream.historical_runtime` or `upstream.reconstruction_runtime`'s shim bookkeeping (both
  Tier C, evaluator-only).
- `limits_applied`: the `ContextSelectionLimits` actually used, so a given run is always
  reproducible/inspectable.

## Failure parsing (`renacir/collector/parsing.py`)

Pure regex parsing of pytest's own textual report — no LLM, never a guess. Handles two report
shapes: the default multi-line report (a `file:line:` trailer plus `E   ` detail lines) and
the condensed `--tb=line` report (one `file:line: ExceptionType: message` line), the latter
used specifically for reconstructed real cases (see below). Any field that can't be determined
with confidence is left `None`/empty — raw `stdout`/`stderr` on `CollectorOutput` always
preserve the full underlying evidence regardless of what parsing extracts.

Frame paths are normalized via `Path.relative_to`, not lexical string matching, and any frame
resolving outside the staged case root — or into `venv/`, `site-packages/`, `__pycache__/`,
`.pytest_cache/`, or `.benchmark-cache/` — is dropped. The exception *type* extracted from a
trailer line is kept even when its file path is dropped (an exception type is legitimate
signal regardless of where it occurred).

## Context-selection algorithm (`renacir/collector/context_selection.py`)

Priority order:
1. **Traceback-referenced files** — what the interpreter actually executed; the strongest
   evidence of relevance.
2. **The failing test file itself** — only for an `"original_fixture"` case. Skipped entirely
   for a reconstructed real case (see below).
3. **Local imports of the failing test file** — a narrow, static, one-level AST parse (no
   transitive resolution, no package-internals crawl), only for an `"original_fixture"` case.
   A deliberate supplement for import-category failures, whose traceback is often too shallow
   (just the import statement site) to surface the actually-relevant module on its own.

**Known v1 limitation, not silently fixed**: rule 3 only resolves the *failing test's own*
imports, not transitively. For `import-renamed-helper`, `helpers.py` — the file that defines
the renamed symbol, and arguably where a diagnosis would start reading — is one import hop
beyond what rule 3 reaches from the test file, and it produces no traceback frame either
(Python's own `ImportError` doesn't emit a `file:line:` trailer for the module that failed to
provide the name). `main.py` (which does the failing `from helpers import helper`) is
selected; `helpers.py` itself currently is not. Extending rule 3 to be transitive was
deliberately not done — it wasn't part of the approved design and would weaken the "bounded,
narrow, explainable" property Phase 3 was scoped around.

**Correction (Phase 3 retrieval-diagnostic audit, 2026-09-19)**: an earlier draft of this
section called `helpers.py` "the most diagnostically relevant file" for this case, without
distinguishing that from "the file the historical repair touches." They are different
questions — the reference repair for `import-renamed-helper` modifies only `main.py`'s import
statement; `helpers.py` is never itself touched by the fix (checked directly against
`reference/fix.patch`). Under `renacir.evaluation.retrieval`'s repair-touched-files definition
(see below), this case actually shows **complete** recall (`main.py` is both the only
reference-relevant file and already selected), not incomplete — the single-hop limitation is
real and worth stating, but this specific case doesn't demonstrate it under a precise
definition of "relevant." `httpie-custom-host-header` (see below) is the case that
demonstrates genuinely incomplete (zero) recall.

## Retrieval-completeness diagnostic (Phase 3 audit, evaluator-only)

`renacir.evaluation.retrieval` (`src/renacir/evaluation/`, deliberately **outside**
`renacir.collector` — nothing in Collector imports it, nothing here is reachable from
`collect()`) computes a `RetrievalDiagnostic` for an already-produced `CollectorOutput`,
strictly after the fact:

- `selected_file_count`, `selected_total_chars`, `selected_total_lines`, `selection_reasons`
  (a count per `SelectedFileReason`), `empty_context`, `truncation_occurred` — summary
  statistics over `CollectorOutput.selected_context`, computed with no reference-repair
  knowledge at all.
- `reference_relevant_files_available/_retrieved/_total` and `reference_relevant_file_recall`
  — compares `selected_context`'s paths against `reference_relevant_files(case)`: for a real
  case, `upstream.production_files` (already-recorded provenance, read directly); for a
  synthetic case, the `+++ b/<path>` headers parsed out of the stored `fix.patch`. `None`
  (never a fabricated `False`/`0`) when no file list can be derived at all.

**This measures the existing policy; it does not change it.** No selection rule, limit, or
default was modified to produce this diagnostic or to make any case's recall look better.
`compute_retrieval_diagnostic` is pure and read-only with respect to the `CollectorOutput` it
scores — it cannot feed back into `selected_context`, `stdout`, `stderr`, `parsed_failure`, or
`context`, because it only ever runs after `collect()` has already returned. Proven by
`tests/evaluation/test_retrieval.py::test_reference_relevance_cannot_influence_collection`.

**What this diagnostic explicitly is not** — stated directly, not left implicit:
- **Not** a claim that reference-repair-touched files are the only relevant files for
  diagnosis (`helpers.py` above is a real counterexample: relevant to understanding the bug,
  absent from the repair-touched set).
- **Not** a semantic-relevance or context-quality measure — it is a bounded proxy over exact
  path matches only.
- **Not** a predictor of diagnosis success — a recall of 1.0 does not mean a future Diagnoser
  would succeed, and a recall of 0.0 does not mean it would necessarily fail.

**Measured, not adjusted, results** (see `docs/decisions.md`'s Phase 3 audit entry for the
full table): `assertion-average-off-by-one` — recall 1.0. `import-renamed-helper` — recall 1.0
(corrected from the earlier "incomplete" assumption above). `httpie-custom-host-header` —
recall 0.0, `empty_context: true` (its only traceback frame is the withheld retrospective
overlay, so rule 1 finds nothing selectable and rules 2/3 don't run for a reconstructed case at
all). Both the 1.0 and 0.0 results are kept as measured.

Every selected file is truncated to `ContextSelectionLimits.max_lines_per_file` /
`.max_chars_per_file`; selection stops at `.max_files` or `.max_total_context_chars`, checked
in priority order. Limits are explicit, conservative, configurable defaults — not derived from
data (the same methodological status as `source.repository_size` being descriptive, not a hard
gate) — recorded on every `CollectorOutput.limits_applied` for reproducibility:

| Limit | Default |
|---|---|
| `max_files` | 5 |
| `max_lines_per_file` | 200 |
| `max_chars_per_file` | 20,000 |
| `max_total_context_chars` | 60,000 |
| `max_stdout_chars` | 10,000 |
| `max_stderr_chars` | 10,000 |

## Retrospective test overlays — the information-boundary decision

For a real case whose failing test is a retrospective regression test (`case.test_overlay is
not None` — true for all 3 current REAL-CI-C cases, per `docs/benchmark_schema.md`), Collector
resolves a genuine tension: it must execute that test to observe the failure at all (there is
no other way to reproduce the historical bug), but Phase 2E already established that a
retrospective overlay's source text must never be model-facing.

**The approved resolution, implemented exactly as specified:**

- The overlay **may** be applied internally (`apply_test_overlay`, reused as-is from
  `renacir.benchmark.runner`) to reconstruct and execute the historical failure.
- Collector **may** observe and report the resulting execution evidence: `stdout`, `stderr`,
  `exit_code`, the parsed exception type/message, traceback frame `file:line` locations, and
  the failing node id (already string-only, via `ModelFacingContext.failing_test`).
- The overlay's source text **must not** appear anywhere in `CollectorOutput` — `selected_context`
  never includes it, even when a traceback frame points directly at it (`context_selection.py`
  categorically excludes `case.test_overlay.target_path`, checked before every other selection
  rule, regardless of which rule would otherwise pick it up).
- `CollectorOutput.failing_test_provenance` is the explicit provenance/availability signal: a
  future Diagnoser can see `"reconstructed_retrospective_overlay"` and know a failure was
  reconstructed this way, without ever receiving the withheld content.
- For a reconstructed case, `collect()` additionally runs pytest with `--tb=line` instead of
  the default report format. Pytest's default multi-line report embeds source-context lines
  around the failing call *from the test file itself* — even without Collector deliberately
  reading that file, raw `stdout` would otherwise echo overlay source. `--tb=line` gives one
  line per frame (`file:line: ExceptionType: message`, no source snippet) — `stdout` stays
  populated with real evidence, just never a source excerpt of the withheld file.

**This is a deliberate asymmetry, not an inconsistency**: for an `"original_fixture"`
(synthetic) case, the failing test's source is legitimately Tier B and appears in
`selected_context` under the normal bounded rules, with the default (richer) pytest report
format. Both behaviors are driven by the same single field, `case.test_overlay`, checked in
exactly two places (`context_selection.select_context`'s rule 2/3 gate, and `collector.collect`'s
`--tb=line` branch) — not duplicated ad hoc logic.

## Determinism and path redaction

Three implementation discrepancies were found and fixed before the test suite was considered
complete — all violated determinism and/or leaked local filesystem layout, none affected the
information-boundary guarantee above:

1. **Stale bytecode caches.** `staged_case()`'s copy includes any pre-existing
   `__pycache__`/`.pytest_cache` directories from the original fixture (left over from earlier
   direct `pytest -q` runs, per the README's manual-reproduction workflow). Their `.pyc` files
   embed the *original* fixture's absolute path in debug info and, because `shutil.copytree`
   preserves mtimes, can be reused instead of recompiled — causing pytest's traceback trailer
   to print that stale absolute path instead of one relative to the current run's temp
   directory. Fixed by purging both directories from Collector's own staged copy before running
   (`_purge_stale_caches`) — scoped to Collector only, never touches the original fixture or
   `renacir.benchmark.runner`'s shared behavior.
2. **Non-deterministic absolute paths in exception text.** Python's own exception messages
   (e.g. `ImportError`) and pytest's own scratch fixtures (`tmp_path`, used inside
   `click-path-resolve-symlink`'s test — its path embeds the OS username and a per-run
   counter) can embed absolute paths pointing into the randomized staged tempdir or the system
   temp root. Fixed by redacting `staged_root`, `cache_root`, and any residual path under
   `tempfile.gettempdir()` to stable placeholders (`<case-root>`, `<reconstruction-cache>`,
   `<tmp>`) — applied only to what's *stored/displayed*, never to what `parse_failure` parses
   (parsing needs real paths to resolve frames correctly; redacting first was tried and found
   to silently empty out context selection).

Both fixes are prerequisites for `tests/collector/test_collector.py`'s determinism tests
(`test_collect_is_deterministic_across_repeated_runs`, `..._for_import_case`,
`..._for_a_real_case`), which assert full `CollectorOutput` equality across repeated runs of
the same case.

## What remains intentionally unresolved

- The retrieval-completeness diagnostic referenced by `docs/research_protocol.md`'s unresolved
  item 12 is now implemented (`renacir.evaluation.retrieval`, above) — but implementing the
  *measurement* doesn't resolve the broader methodology question that item was tracking: what
  threshold or aggregate reporting policy (if any) turns per-case recall into a benchmark-level
  claim, how repo-clustering interacts with it, and whether/how it should factor into
  correctness-tier or Gatekeeper analysis are all still open. Empty/incomplete context is
  intentionally left observable rather than silently repaired before Diagnoser evaluation —
  that is the point of this diagnostic, not a gap in it.
- Rule 3's non-transitivity (see above) is a known, stated v1 gap, not a bug — this diagnostic
  measures it (see `httpie-custom-host-header`'s recall above) rather than fixing it, per the
  explicit instruction that this step measures the policy, it does not improve it.
- No live GitHub Actions ingestion, no LLM, no GitHub API integration — all explicitly out of
  scope for this phase (`ARCHITECTURE.md`'s safety constraints still apply project-wide).
- Collector does not yet feed a Diagnoser — nothing downstream of `CollectorOutput` exists.
