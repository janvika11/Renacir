# Benchmark Schema and Information Boundaries

**Status: Phase 2A/2B/2E, 2026-09-18.** Documents the manifest schema and the four information
tiers introduced by the Phase 2 curation methodology (`docs/research_protocol.md`,
`docs/decisions.md`). Phase 2A built the schema; Phase 2B grew the benchmark from 2 to 9
synthetic pilot cases; Phase 2E added a first, verified real-world pilot (3 REAL-CI-C cases,
reconstruction-recipe architecture, no upstream vendoring). **This is still a pilot, not the
final research benchmark** — the ~30–50 case target is unmet, and 3:9 real:synthetic is not
claimed as a final or representative ratio.

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
| **D — reference-repair-only** | Strictly hidden, no exceptions | Each case's `reference/` directory | `reference_repair.patch`, `independent_check.py` (Phase 2B), `repro_test.py`/`test_overlay` (Phase 2E, real cases only — see below) |

**Enforcement is by type, not by file location alone — and, as of Phase 2B, also by staging
behavior.** `renacir.benchmark.context.py` defines `ModelFacingContext` as an explicit
allowlist — it has no field that overlaps with `SourceMetadata`, `CurationMetadata`,
`ContaminationRisk`, `ReferenceRepair`, or `IndependentCheck` (checked by
`tests/benchmark/test_context.py`), and `build_model_facing_context()` reads only
`BenchmarkCase.failing_test`, `.command`, and `.category`. This exists so that when a future
Collector is implemented, it has a fixed shape to build its output into, rather than passing
an arbitrary benchmark dictionary forward and hoping the sensitive fields are never read.
Collector does not exist yet; nothing in this repository calls or depends on one.

**Discovered and fixed during Phase 2B**: `renacir.benchmark.runner.staged_case` originally
copied a case's *entire* directory — including `reference/` — into the isolated temp
directory each test run executes in. This never affected reported pass/fail results (nothing
under `reference/` matched pytest's test-discovery pattern), but it meant Tier D material was
physically present in the same directory tree a future Collector would naturally scan,
undermining the tiering independent of what `ModelFacingContext` itself exposes. Fixed by
excluding `reference/` from the staged copy entirely; the reference-repair patch is now read
directly from the original case directory when applied, and independent-check files are
copied in individually, one at a time, only *after* the repair has already been applied.
Verified by `tests/benchmark/test_context.py::test_staged_case_never_contains_reference_directory`.

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
requirement. The 9 synthetic fixtures are pure-stdlib and need nothing beyond Python 3.11+.
The 3 Phase 2E real cases are the first cases to actually exercise this: each has its own
pinned, non-trivial dependency set (`requests`, `Pygments`, `click` itself, etc.), recorded via
`upstream.preparation_steps` rather than `execution.dependency_spec`/`.install_procedure`
(which are `None` for these cases — reconstruction-recipe cases use the richer
`upstream`-scoped runtime/dependency fields instead; see "Real-world cases" above). **This
confirms the eventual Validator sandbox (Phase 3) will need case-specific runtime
images/environments, not one fixed Renacir-wide image** — Phase 2E's per-case venv (created by
`prepare_case`, never Renacir's own dev environment) is a working small-scale precedent for
that, not yet the Phase 3 Docker-sandboxed design itself.

## Independent correctness checks (Phase 2B)

`IndependentCheck` (`path`, `description`) records an evaluator-only test beyond the
originally-failing one — a boundary sweep, a cross-call state check, an import-signature
check, etc., per `docs/research_protocol.md` §7.1(c). `path` always points inside
`reference/` (Tier D). `renacir.benchmark.runner.run_independent_checks` copies each check
file into the staged directory individually, only after the reference repair has already been
applied, and runs it by explicit filename (`pytest <file> -q`) — never relying on pytest's
ordinary auto-discovery, so a check file is never accidentally collected during the pre-repair
run or by a bare `pytest -q` elsewhere. 7 of the 9 current cases have one; the 2 original
Phase 1 cases do not yet (a recorded gap, not an inconsistency — see
`docs/research_protocol.md`'s unresolved item 2 on held-out-test coverage).

## Candidate curation records

`benchmarks/candidates.json` (schema in `renacir.benchmark.curation`) holds
`CandidateCurationRecord` entries for candidates that were reviewed — `accepted`, `rejected`,
or (Phase 2E) `held` — kept structurally separate from `manifest.json`. A rejected or held
candidate has no path, command, or reference repair; neither is ever required to become an
executable `BenchmarkCase`, and the two are never conflated (`held` = a confirmed real bug not
implemented for a documented methodological reason; `rejected` = found unsuitable). As of
Phase 2E, holds 6 records: the Phase 2B synthetic rejection (`assertion-tax-wrong-constant`,
substantially redundant with `assertion-average-off-by-one`); two real-world holds
(`tqdm-tenumerate-start`, `thefuck-pip-unknown-command` — see the REAL-CI taxonomy above); and
the 3 accepted real cases, each with `benchmark_case_id` pointing at its manifest entry.

## Benchmark fixtures are excluded from Renacir's own lint config (Phase 2B)

Discovered while adding `import-reportpkg-broken-init`: its intentional bug (`__init__.py`
importing a symbol that no longer exists) is also, incidentally, an unused-import lint error
under Renacir's own ruff rules (`F401`), since the earlier 8 fixtures' bugs happened not to
trip any selected rule. Fixtures are deliberately-broken sample code under test, not code that
should meet the project's own lint bar. Fixed by adding `extend-exclude = ["benchmarks"]` to
`[tool.ruff]` in `pyproject.toml`, rather than reshaping a fixture's bug to dodge a linter.

## Real-world cases (Phase 2E): the REAL-CI-A/B/C taxonomy

A real-world candidate qualifies for the executable benchmark only if primary-source evidence
demonstrates that, **before** the historical repair, one of the following existed:

- **REAL-CI-A** — a failing automated test already present in the repository.
- **REAL-CI-B** — a preserved CI run/log demonstrating the failure.
- **REAL-CI-C** — a bug report containing a reproducible failing test/command that predates
  the repair. This does **not** mean the pytest regression artifact that later catches the bug
  existed before the fix — most mature open-source projects add their regression test
  *alongside* the fix commit (a "retrospective regression test"). REAL-CI-C requires only that
  the *failure itself* — its specification and reproduction evidence — is shown to predate the
  repair, via the issue/bug report. Conflating "the failure predates the fix" with "the pytest
  artifact predates the fix" is a methodological error this taxonomy exists to prevent.

A candidate that is a real, reproducible historical bug but does **not** meet this bar (e.g.
the buggy and fix commits are minutes apart on the same feature branch, with no independent
pre-fix evidence of the failure) is recorded as **HOLD — REAL-HISTORY/RETROSPECTIVE-TEST** in
`benchmarks/candidates.json` (`decision: "held"`) — not `"rejected"`. A held candidate is a
valid investigation, preserved, never silently reclassified as invalid.

**All 3 Phase 2E cases are REAL-CI-C.** No REAL-CI-A or REAL-CI-B candidate has been found —
this was searched for directly (a "zero test files touched in the fix commit" screening
heuristic across 20+ commits in 5+ repositories) and is recorded as a genuine negative finding,
not a search gap. Two candidates (`tqdm-tenumerate-start`, `thefuck-pip-unknown-command`) were
fully reproduced and are held for exactly this reason.

## Real-world cases (Phase 2E): reconstruction recipes, not vendoring

Real cases never carry vendored upstream production source in this repository. Instead,
`BenchmarkCase.upstream` (`UpstreamProvenance`, `None` for every synthetic case — never given
placeholder/fabricated values) records:

- **Provenance**: `repository`, `repository_url`, `license`, `license_verification_note`,
  `issue_url`/`issue_date`, `buggy_commit`, `fix_commit`/`fix_date`, `production_files`,
  `real_ci_subtype`.
- **Two distinct runtimes**: `historical_runtime` (what's known about the *original*
  environment — fields `None` where genuinely unknown, never claimed more precisely than the
  evidence supports) and `reconstruction_runtime` (the environment actually verified this
  project, plus `compatibility_adaptations` — narrow, documented shims like
  `collections.Iterable` → `collections.abc`, needed only because no historically-accurate
  interpreter is available locally, and which never touch `production_files`).
- **The reconstruction recipe itself**: `preparation_steps` (`PreparationStep`: `argv` + `cwd`,
  executed directly, never through a shell) — clone the pinned repository, checkout the pinned
  `buggy_commit`, create a venv, install dependencies. `package_root` says where the importable
  package lives in the checkout (`"."` for a flat layout, `"src"` for a src layout).
- **Preparation vs. evaluation**: `preparation_requires_network` / `evaluation_requires_network`
  — `renacir.benchmark.reconstruction.prepare_case` is the *only* function in Renacir that may
  reach the network for a real case, is idempotent, and never applies the reference repair.
  `renacir.benchmark.runner.evaluate_case` never calls it implicitly — an unprepared real case
  raises `PreparationRequiredError` rather than silently reaching the network. Once prepared
  (`.benchmark-cache/<id>/`, git-ignored, no `.git` directory — no reachable future/fix history
  sits in the local cache), evaluation is fully offline.

`renacir.benchmark.runner._subprocess_env` prepends the reconstruction cache's own venv to
`PATH` and the staged checkout's `package_root` to `PYTHONPATH`, so `case.command` always
imports the package from the *currently staged* (pre- or post-repair) copy — never a stale
editable-install reference back into the persistent cache (a real bug hit and fixed during
Phase 2E: `pip install -e` for a real case points imports back at the cache regardless of what
gets patched in the staged copy, silently defeating the reference-repair application).

## Real-world cases (Phase 2E): the retrospective-test leakage boundary

Where a real case's failing test is itself a retrospective regression test (true for all 3
Phase 2E cases), it is stored as `reference/repro_test.py` and referenced by
`BenchmarkCase.test_overlay` (`RetrospectiveTestOverlay`: `path`, `target_path`) — Tier D, like
`reference/fix.patch`. Unlike independent checks (post-repair only), this file must be present
for *both* the pre- and post-repair evaluator runs, which creates a leakage risk ordinary
`reference/` exclusion doesn't cover: if `staged_case()` copied it into the tree it yields, a
future Collector calling `staged_case()` directly would see it too.

**Fixed by construction, not by convention**: `staged_case()` never copies `test_overlay` — it
stays exactly as pure as it is for a synthetic case. `renacir.benchmark.runner.apply_test_overlay`
copies the file in only on `evaluate_case`'s own private staged instance, called directly by
`evaluate_case` (mirroring how `apply_reference_repair` is applied *outside*, not inside,
`staged_case`). A caller that only uses `staged_case()` never observes this file, regardless of
`evaluate_case`'s internal use of it. Verified by
`tests/benchmark/test_context.py::test_staged_case_never_contains_test_overlay_target`.

Independently, `ModelFacingContext` is unaffected either way: it already only ever carries
`failing_test`/`command` as bare strings (never file content), so no new field was added to it
for real cases — `UpstreamProvenance`'s and `RetrospectiveTestOverlay`'s fields were added to
`tests/benchmark/test_context.py`'s Tier C/D disjointness check for structural completeness, not
because a new leak path was found in `ModelFacingContext` itself.

## Real-world cases (Phase 2E): source grouping and licensing

The two `httpie-*` cases share `source_group_id: "real:httpie-cli"` (same upstream repository);
`click-path-resolve-symlink` has its own, `"real:pallets-click"` — reflecting genuine shared
provenance, per the same principle as synthetic template-sharing groups, never forced into
artificial per-case independence.

All 3 cases' stored `reference/` artifacts (a several-line unified diff, a small
Renacir-authored-or-adapted test file) are from BSD-3-Clause-licensed repositories, verified
against each repository's `LICENSE`/`LICENSE.rst` file at the pinned commit, with attribution
recorded in `reference_repair`'s and `repro_test.py`'s provenance comments. This is a
deliberate, narrower choice than vendoring: the buggy *production* source is never stored here
at all (always freshly cloned by `prepare_case`); only these small, permissively-licensed,
attributed, evaluator-authored-or-derived artifacts are.

## Real-world cases (Phase 2E): reproducibility

Each of the 3 cases was verified through the full `prepare` → `evaluate_case` cycle ≥5
consecutive times: deterministic pre-repair failure, deterministic post-repair success,
deterministic independent-check pass — the same `reproducibility_check_version:
"pilot-5x-v1"` heuristic as synthetic cases (still a pragmatic pilot rule, not a statistical
non-flakiness guarantee). For `click-path-resolve-symlink` specifically, the independent
check's two unaffected sub-cases (an absolute-target symlink; a plain non-symlinked path) were
additionally confirmed to pass on the *buggy* checkout too, not just the repaired one —
demonstrating they are genuine regression guards, not accidentally bug-sensitive.

## What remains unresolved (unaffected by this schema)

Repository-level split scheme (LORO / grouped k-fold / fixed), real:synthetic ratio, exact
sandbox resource/time limits, calibration-summary methodology beyond ruling out naive ECE,
conformal method choice, K repeated runs and aggregation policy — all exactly as unresolved
as recorded in `docs/research_protocol.md` and `docs/decisions.md`. This document is schema
infrastructure; it does not narrow any of those.
