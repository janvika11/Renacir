# Renacir

**Status: Phase 0 complete. Phase 1 benchmark/fixture infrastructure complete (preliminary).**
A minimal, runnable FastAPI skeleton exists (`/health`, config, CI, Docker); no agent code yet.
The benchmark harness (fixture discovery, ground-truth-patch runner, CLI) is built and passing,
but the benchmark itself currently contains only **2 synthetic cases** (one assertion, one
import failure) — nowhere near the ~30–50 curated cases `EVALUATION_PLAN.md` targets. Collector
and Diagnoser (the rest of Phase 1) are not yet implemented.

Renacir studies **confidence-aware selective prediction for autonomous code repair**: given an
LLM-generated patch for a failing Python/PyTest CI build, when is it safe to propose as a pull
request, and when should the system abstain and escalate to a human instead? The repair
pipeline exists to produce the (patch, correctness) pairs needed to study that gating decision
— it is a testbed, not the project's end goal.

- What this is, research question, scope, non-goals: [`PROJECT_SPEC.md`](PROJECT_SPEC.md)
- System components and data flow: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Baselines, metrics, benchmark, experiments: [`EVALUATION_PLAN.md`](EVALUATION_PLAN.md)
- Dated decision log and literature checkpoint: [`docs/decisions.md`](docs/decisions.md)

## How this project will be developed

Phased, with an explicit approval checkpoint between phases:

| Phase | Work |
|---|---|
| 0 | Repo scaffolding, CI for Renacir itself — **done** |
| 1 | Collector + Diagnoser, **+ dataset curation in parallel** — fixture/benchmark infra **done (preliminary, 2 cases)**; Collector + Diagnoser **not started** |
| 2 | Patcher (no sandbox yet) |
| 3 | Docker validation sandbox + Validator |
| 3.5 | Literature checkpoint before designing the gate — **done**, see `docs/decisions.md` |
| 4 | Gatekeeper: baselines first, then evaluate whether calibration is appropriate |
| 5 | 4-condition evaluation harness |
| 6 | Run comparison, calibration analysis, honest write-up |

No component merges to main automatically, and no generated code runs outside the isolated
Docker sandbox described in `ARCHITECTURE.md` — hard constraints, not defaults to relax later.

## Backend structure

```
src/renacir/
├── main.py       # FastAPI app + router registration
├── config.py     # environment-variable-based settings (pydantic-settings)
├── api/          # route definitions (thin — delegate to services)
├── models/       # Pydantic request/response and domain models
├── services/     # business logic, called by the API layer
└── utils/        # small cross-cutting helpers (e.g. logging setup)
```

This is a plain layered structure, not a framework — each layer is a regular Python module, kept separate so future pipeline components (Collector, Diagnoser, etc.) have an obvious place to live without main.py growing into a dumping ground.

## Benchmark

**Pilot — 12 cases (9 synthetic + 3 real).** `benchmarks/` holds a small, deterministic set of
Python projects, each with an intentionally introduced (or historical) failure, a test that
reproduces it, and a **reference repair** — the fixture system Collector/Diagnoser/Patcher will
eventually be evaluated against (see `EVALUATION_PLAN.md`). Phase 2A (schema migration), Phase
2B (synthetic pilot expansion), and Phase 2E (real-world pilot) are complete. **This is still a
pilot, not the final research benchmark** — the ~30–50 case target (`EVALUATION_PLAN.md`) is
unmet, and 3:9 is not claimed as a final or representative real:synthetic ratio. See
`docs/benchmark_schema.md` for the full schema and information-boundary design, and
`docs/research_protocol.md` / `docs/decisions.md` for the methodology behind it.

5 assertion-category and 4 import-category cases, across 6 source groups (some cases
deliberately share a group because they're mutations of the same small template project —
see "Source grouping" below):

- **assertion-average-off-by-one** — off-by-one denominator arithmetic error.
- **assertion-discount-boolean-logic** — wrong boolean operator (`and`/`or`) in a conditional.
- **assertion-tags-mutable-default** — mutable-default-argument state leaking across calls.
- **assertion-truncate-empty-edge-case** — boundary comparison operator (`<`/`<=`) error.
- **assertion-config-fallback-default** — wrong fallback/default value for a missing key.
- **import-renamed-helper** — stale import name after a rename in a sibling module.
- **import-reportpkg-missing-reexport** — a package `__init__.py` never re-exports a symbol
  that works fine when accessed directly.
- **import-reportpkg-bad-local-import** — an absolute import inside a function body that
  should have been relative; fails only when the function is called, not on import.
- **import-reportpkg-broken-init** — a package `__init__.py` itself references a symbol
  removed in an earlier refactor, breaking the entire package's import, not just one path.

3 real-world **REAL-CI-C** cases (Phase 2E — see "Real-world (REAL-CI-C) cases" below):

- **httpie-none-header-skip** — `httpie/cli` issue #412: `Session.update_headers()` crashes on
  a `None`-valued header during `--download` within `--session`.
- **httpie-custom-host-header** — `httpie/cli` issue #235: a custom `Host` header is duplicated
  because the presence check runs against a dict copy instead of the original headers.
- **click-path-resolve-symlink** — `pallets/click` issue #1921: `click.Path(resolve_path=True)`
  resolves a relative symlink against the process cwd instead of its own containing directory.

**Source grouping**: `assertion-tags-mutable-default` and `assertion-truncate-empty-edge-case`
share `synthetic:textstats-template`; the three `import-reportpkg-*` cases share
`synthetic:reportpkg-template`; the two `httpie-*` cases share `real:httpie-cli` (same upstream
repository); `click-path-resolve-symlink` has its own group, `real:pallets-click` — genuinely
related mutations/commits, not artificially split into independent groups. See
`docs/benchmark_schema.md` for the full distribution and `docs/decisions.md`'s Phase 2B/2E
entries for the reasoning behind every case, including one synthetic candidate
(`assertion-tax-wrong-constant`) rejected as redundant before being built, and two real-world
candidates (`tqdm-tenumerate-start`, `thefuck-pip-unknown-command`) **held** — real,
reproduced bugs not implemented as executable cases because no primary-source evidence shows
the failure predates its fix (see REAL-CI taxonomy below) — all recorded in
`benchmarks/candidates.json`, none silently dropped.

Each **synthetic** case lives under `benchmarks/cases/<id>/` and contains:

```
<case>/
├── *.py              # the minimal buggy project + its failing test
├── case.json         # category, description, root cause
└── reference/
    ├── fix.patch               # reference repair — restores passing state; not the only
    │                           # semantically valid repair, and not a syntactic target
    │                           # (see docs/research_protocol.md §7)
    └── independent_check.py    # optional — an evaluator-only correctness check beyond
                                # the originally-failing test (present for all 7 Phase 2B
                                # cases; not yet added to the original 2)
```

Each **real** case's directory is deliberately smaller — no upstream source is vendored:

```
<real-case>/
├── case.json          # category, description, root cause
└── reference/
    ├── fix.patch               # the historical repair, derived from the pinned fix commit
    ├── repro_test.py           # a network-free reproduction (Renacir-authored, or adapted
    │                           # from the historical regression test) — see "Real-world" below
    └── independent_check.py    # evaluator-only correctness check
```

`benchmarks/manifest.json` is the machine-readable index `src/renacir/benchmark/` reads to
discover and run cases — execution metadata (id, category, path, command, failing test,
runtime/environment info), source metadata (synthetic vs. real, source-group grouping for
future repo-clustering analysis), curation metadata (accept/reject status, fold placeholder,
contamination-risk flags), the reference repair's patch path, and any independent
correctness checks. See `docs/benchmark_schema.md` for the full field reference and which
fields are safe for a future model-facing context versus evaluator-only.

`benchmarks/candidates.json` separately records real-world **and** synthetic candidate
curation decisions — `accepted` (implemented), `rejected` (invalid/irreproducible/unsuitable),
or `held` (a confirmed real bug, not implemented for a documented methodological reason, never
conflated with `rejected`) — that are not, and never need to become, executable benchmark
cases. Holds: `assertion-tax-wrong-constant` (synthetic, rejected as redundant with
`assertion-average-off-by-one`); `tqdm-tenumerate-start` and `thefuck-pip-unknown-command`
(real, held — see REAL-CI taxonomy below); and the 3 accepted real cases, each pointing at its
`benchmark_case_id`.

**List cases:**

```bash
python -m renacir.benchmark list
# or, after `pip install -e .`:
renacir-benchmark list
```

**Reproduce a fixture's failure by hand:**

```bash
cd benchmarks/cases/assertion_average_off_by_one
pytest -q   # fails deterministically
```

**Run a case (or all cases) through the harness** — stages the fixture in an isolated temp
directory, runs its tests (expected to fail), applies `reference/fix.patch` via `git apply`,
then re-runs the tests (expected to pass):

```bash
renacir-benchmark run                              # all cases
renacir-benchmark run assertion-average-off-by-one  # one case
```

The **reference repair** for every case is defined by `reference/fix.patch`: applying it to
the pristine fixture must make the previously-failing test (and the rest of the fixture's
suite) pass, with no other files touched. It restores a *known*-good state and supports
provenance/correctness-check construction — it is not claimed to be the only semantically
valid repair (see `docs/research_protocol.md` §7's tier-1/tier-2/incorrect taxonomy).
`reference/` is never staged into the directory a run's tests execute in *except* to apply
the patch itself and (afterward) to run an independent check — it is excluded from the
general staged copy specifically so Tier D material never sits alongside what a future
Collector would scan (see `docs/benchmark_schema.md`).

10 of the 12 cases also carry an **independent correctness check**
(`reference/independent_check.py`) — an evaluator-only test beyond the originally-failing
one (a boundary sweep, a cross-call state check, an import-signature check, etc.), run
automatically after the reference repair is applied. `renacir-benchmark run` reports its
result alongside the pass/fail outcome; it never appears in `ModelFacingContext`.

### Real-world (REAL-CI-C) cases

The 3 real cases are never vendored — no upstream production source lives in this
repository. Each records a pinned buggy commit, a pinned fix commit, and an explicit
**reconstruction recipe** (`upstream.preparation_steps` in the manifest: clone, checkout,
create a venv, install pinned dependencies) that `renacir.benchmark.reconstruction.prepare_case`
executes to materialize a local, disposable checkout under `.benchmark-cache/` (git-ignored).

This is a deliberate **preparation vs. evaluation** split:

```bash
python -m renacir.benchmark prepare                     # all real cases; needs network
python -m renacir.benchmark prepare httpie-none-header-skip --force
python -m renacir.benchmark run httpie-none-header-skip  # offline once prepared
```

`prepare` is the only thing in Renacir that may need network access for a real case, and it's
idempotent — a case already prepared is a no-op unless `--force` is passed. `run`/`evaluate_case`
never calls `prepare` implicitly; evaluating an unprepared real case raises
`PreparationRequiredError` rather than silently reaching the network. The prepared checkout has
no `.git` directory (no reachable future/fix-commit history sits in the reconstruction cache),
and its own historical dependency stack runs against small, narrow, explicitly-documented
compatibility shims (e.g. `collections.Iterable` → `collections.abc`, needed only because no
historically-accurate Python interpreter is available locally) that never touch the file the
historical bug and fix are actually in.

Each real case is classified **REAL-CI-C**: a pre-fix issue contains a reproducible failing
command/scenario, reconstructed here as a network-free test — but (unlike REAL-CI-A/B) the
*pytest artifact* that catches it may itself have been added alongside the fix (a
"retrospective regression test"). Where that's true, the test lives in `reference/` as a
`test_overlay`, applied only by the evaluator for both the pre- and post-repair runs — like
`reference/fix.patch`, it is never part of the general tree `staged_case()` yields, so it can
never leak into a future model-facing Collector's view. Two real-world candidates
(`tqdm-tenumerate-start`, `thefuck-pip-unknown-command`) were investigated and reproduced but
are **held**, not implemented, because no primary-source evidence shows their failure predates
the fix at all — see `docs/benchmark_schema.md` for the full REAL-CI-A/B/C definition and
`benchmarks/candidates.json` for both held records.

`tests/benchmark/` enforces all of this — pre-patch failure, post-patch success, independent
checks, schema validation, and the Tier B/C/D/reconstruction-recipe boundary — as part of the
normal `pytest` run, so a regression in a fixture, the schema, or the leakage boundary is a CI
failure, not a silent drift. The 3 real cases' reproduction tests are skipped (not failed) in
`tests/benchmark/test_real_cases.py` until `prepare` has been run for them — a fresh clone's
`pytest -q` stays offline and green.

## Pipeline

**Collector — implemented, Phase 3.** The first real pipeline component (`src/renacir/collector/`):
takes a benchmark/reconstructed case, runs its failing test through the existing benchmark
staging infrastructure, and packages deterministic, bounded, model-facing evidence
(`CollectorOutput`) for a future Diagnoser. Collects evidence only — no diagnosis, no patch,
no LLM, no confidence decision. See `docs/collector.md` for the full contract,
context-selection rules, and information-boundary guarantees.

```bash
python -m renacir collect assertion-average-off-by-one
python -m renacir collect httpie-none-header-skip --json   # requires `prepare` first
```

**Diagnoser — offline core only, Phase 4B.** `src/renacir/diagnoser/`: an explicit
`DiagnoserInput` allowlist built from `CollectorOutput`, a versioned prompt renderer, a
minimal provider-neutral `LLMProvider` interface, and strict `Diagnosis` output
parsing/validation with no retry. **No LLM SDK is installed and no real model call has been
made** — everything is exercised through a `FakeProvider` that never touches a network. See
`docs/diagnoser.md` for the full input/output contract, confidence semantics, and what has and
has not been done.

Patcher, Validator, Gatekeeper, and Orchestrator (see `ARCHITECTURE.md`) are all still
unimplemented.

## Local setup

Requires Python 3.11+ (Docker and CI are pinned to 3.11 exactly for reproducibility).

```bash
python3 -m venv .venv
source .venv/bin/activate       # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
cp .env.example .env
```

Run the app:

```bash
uvicorn renacir.main:app --reload
curl http://localhost:8000/health   # {"status":"ok"}
```

Run tests and checks:

```bash
pytest
ruff check .
ruff format --check .
```

Run with Docker:

```bash
docker build -t renacir .
docker run -p 8000:8000 renacir
```
