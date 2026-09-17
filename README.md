# Renacir

**Status: Phase 0 complete.** A minimal, runnable FastAPI skeleton exists (`/health`, config,
CI, Docker); no agent code yet.

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
| 1 | Collector + Diagnoser, **+ dataset curation in parallel** |
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
