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

**Preliminary — 2 synthetic cases.** `benchmarks/` holds a small, deterministic set of
synthetic Python projects, each with an intentionally introduced failure, a test that
reproduces it, and a **reference repair** — the fixture system Collector/Diagnoser/Patcher
will eventually be evaluated against (see `EVALUATION_PLAN.md`). Phase 2A (schema migration
and curation infrastructure) is complete; actual curation toward the ~30–50 case target
(`EVALUATION_PLAN.md`) has **not started** — this is still 2 cases, not a claim of a larger
benchmark. See `docs/benchmark_schema.md` for the full schema and information-boundary
design, and `docs/research_protocol.md` / `docs/decisions.md` for the methodology behind it.
Two failure classes exist so far, matching v1 scope in `PROJECT_SPEC.md`:

- **assertion** — `assertion-average-off-by-one`: an off-by-one denominator produces a wrong
  result instead of crashing, caught only by the test's assertion.
- **import** — `import-renamed-helper`: a dependency module was renamed, leaving a stale
  import that raises `ImportError` before any test logic runs.

Each case lives under `benchmarks/cases/<id>/` and contains:

```
<case>/
├── *.py              # the minimal buggy project + its failing test
├── case.json         # category, description, root cause
└── reference/
    └── fix.patch      # reference repair — restores passing state; not the only
                        # semantically valid repair, and not a syntactic target
                        # (see docs/research_protocol.md §7)
```

`benchmarks/manifest.json` is the machine-readable index `src/renacir/benchmark/` reads to
discover and run cases — execution metadata (id, category, path, command, failing test,
runtime/environment info), source metadata (synthetic vs. real, source-group grouping for
future repo-clustering analysis), curation metadata (accept/reject status, fold placeholder,
contamination-risk flags), and the reference repair's patch path. See
`docs/benchmark_schema.md` for the full field reference and which fields are safe for a
future model-facing context versus evaluator-only.

`benchmarks/candidates.json` separately records real-world candidate curation decisions
(accepted and rejected) that are not, and never need to become, executable benchmark cases —
currently empty, since no real-world curation has happened yet.

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
`tests/benchmark/` enforces reference-repair mechanics — pre-patch failure and post-patch
success, plus schema validation — as part of the normal `pytest` run, so a regression in a
fixture or the schema is a CI failure, not a silent drift.

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
