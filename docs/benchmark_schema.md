# Benchmark Schema and Information Boundaries

**Status: Phase 2A infrastructure, 2026-09-18.** Documents the manifest schema and the four
information tiers introduced by the Phase 2 curation methodology
(`docs/research_protocol.md`, `docs/decisions.md`). This is infrastructure, not curated data
— the benchmark still contains only the 2 original synthetic cases. No real-world case has
been curated; no dataset has been imported.

## Terminology: reference repair, not gold patch

What Phase 1 called `expected_repair` is now `reference_repair` everywhere (schema field,
Pydantic class, and each case's `expected/` directory is now `reference/`). This is not a
cosmetic rename: it reflects a substantive decision from the Phase 2 methodology review. A
reference repair —

- **is** a known-good state (a fix that restores passing tests with no regressions),
- **is** useful for provenance, for constructing independent correctness checks, and for
  understanding intended behavior,
- **is not** claimed to be the only semantically valid repair for a case,
- **is not** a syntactic target — correctness never requires structural similarity to it.

This is unchanged from, and now consistently named after, the tier-1/tier-2/incorrect
correctness taxonomy already frozen in `docs/research_protocol.md` §7.

## The four information tiers

| Tier | Meaning | Where it lives | Example fields |
|---|---|---|---|
| **A — execution** | Needed to run the case at all | `manifest.json`, per case: `execution` block | `python_version`, `dependency_spec`, `install_procedure`, `environment_info`, `reproducibility_check_version` |
| **B — potentially model-facing** | What a real CI repair system would legitimately see at failure time | Built by explicit allowlist, `renacir.benchmark.context.ModelFacingContext` — **not** simply "whatever isn't in tier D" | `failing_test`, `command`, `category`, `repository_identity` (currently always `None` — see below) |
| **C — evaluator-only** | Used for scoring/statistical analysis; never shown to a model | `manifest.json`, per case: `source`, `curation` blocks | `source_group_id`, `repository_size`, `curation.status`, `dedup_cluster_id`, `fold`, `contamination_risk` |
| **D — reference-repair-only** | Strictly hidden, no exceptions | Each case's `reference/` directory | `reference_repair.patch`, (future) `provenance.json`, `held_out_test.py`, differential-check fixtures |

**Enforcement is by type, not by file location alone.** `renacir.benchmark.context.py`
defines `ModelFacingContext` as an explicit allowlist — it has no field that overlaps with
`SourceMetadata`, `CurationMetadata`, `ContaminationRisk`, or `ReferenceRepair` (checked by
`tests/benchmark/test_context.py`), and `build_model_facing_context()` reads only
`BenchmarkCase.failing_test`, `.command`, and `.category`. This exists so that when a future
Collector is implemented, it has a fixed shape to build its output into, rather than passing
an arbitrary benchmark dictionary forward and hoping the sensitive fields are never read.
Collector does not exist yet; nothing in this repository calls or depends on one.

## Repository identity: an explicit, unresolved design variable

`ModelFacingContext.repository_identity` exists as a field and is currently always `None`.
Per the Phase 2 methodology revision, whether to expose upstream repository/library identity
to a future Collector is **not resolved** — there is a real trade-off (exposing it is more
representative of real CI usage; hiding it reduces memorization/contamination risk) and
`docs/research_protocol.md` deliberately does not pick a side. A future identity-exposed vs.
identity-redacted comparison is a candidate experiment, not a decision made here. Whatever is
eventually decided, provenance and reference-repair data (Tier D) remain hidden regardless —
that part is not in question.

## Reproducibility: a pilot rule, not a guarantee

`execution.reproducibility_check_version` (e.g. `"pilot-5x-v1"`) records which version of the
reproducibility-checking procedure a case was validated under — currently, ≥5 identical
pre-repair reruns. This is a pragmatic curation heuristic carried over from Phase 1, **not** a
statistically derived guarantee of non-flakiness. If evidence of flakiness surfaces later,
the procedure is revisited and the version string changes — old cases keep their original
version tag rather than silently being reinterpreted under a new rule. No code in this
repository claims that passing this check proves determinism.

## Case-specific runtime

`execution.python_version`, `.dependency_spec`, `.install_procedure`, and `.environment_info`
record what a *case* needs to run — which may differ from Renacir's own Python 3.11+
requirement. Both current fixtures are pure-stdlib and need nothing beyond Python 3.11+, but
a future real case (a historical bugfix commit) may require an older, pinned Python version
and dependency set. **This means the eventual Validator sandbox (Phase 3) will likely need
case-specific runtime images or environments, not one fixed Renacir-wide image** — recorded
here as a forward implication for that design, not solved now.

## Candidate curation records

`benchmarks/candidates.json` (schema in `renacir.benchmark.curation`) holds
`CandidateCurationRecord` entries for real-world candidates that were reviewed — accepted or
rejected — kept structurally separate from `manifest.json`. A rejected candidate has no path,
command, or reference repair; it is never required to become an executable `BenchmarkCase`.
Currently empty: no real-world candidate has been reviewed yet.

## What remains unresolved (unaffected by this schema)

Repository-level split scheme (LORO / grouped k-fold / fixed), real:synthetic ratio, exact
sandbox resource/time limits, calibration-summary methodology beyond ruling out naive ECE,
conformal method choice, K repeated runs and aggregation policy — all exactly as unresolved
as recorded in `docs/research_protocol.md` and `docs/decisions.md`. This document is schema
infrastructure; it does not narrow any of those.
