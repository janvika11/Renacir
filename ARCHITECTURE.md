# Architecture

Renacir's repair pipeline exists to produce (patch, correctness) pairs for studying the
confidence gate — it is the testbed, not the end goal (see `PROJECT_SPEC.md`).

## Components

**Collector**
Input: a failed GitHub Actions run (repo, commit, workflow logs).
Output: failing test output, the diff/commit under test, and the minimal set of repo files
relevant to the failure (the failing test file plus its direct dependencies).

**Diagnoser**
Input: the Collector's output.
Output: a root-cause hypothesis grounded in cited log/source lines, plus a stated confidence.
Implementation: a single LLM call in v1 — no multi-step agent loop.

**Patcher**
Input: the Diagnoser's hypothesis and the relevant files.
Output: a minimal unified diff addressing the diagnosed cause, constrained to the files
already identified as relevant.
Implementation: a single LLM call in v1.

**Validator**
Input: the proposed diff.
Action: applies the diff in an isolated, ephemeral Docker container (no network access,
CPU/memory/time limits, non-root user) and re-runs the failing test plus the full suite.
Output: pass/fail for the target test, plus a regression flag if previously-passing tests
now fail.

**Gatekeeper**
Input: candidate gate signals — Validator outcome (always included), and, pending the
ablation study in `docs/research_protocol.md` §9, diagnosis confidence and patch
characteristics (diff size, files touched, retry count). Diagnoser confidence is not
assumed calibrated; whether to include it as a gate input is an empirical question, not a
settled design choice.
Output: propose-as-PR or escalate-to-human, with the evidence trail behind the decision.
This is the object of study — see `EVALUATION_PLAN.md` and `docs/research_protocol.md`.

**Orchestrator**
Sequences Collector → Diagnoser → Patcher → Validator → Gatekeeper and logs every
intermediate artifact; that log is the dataset the evaluation phase analyzes.
Implementation: hand-rolled, not a framework (LangGraph/CrewAI/etc.), to keep the gate
decision fully inspectable — a stated project decision, not a claim that frameworks are
unsuitable in general (see `docs/decisions.md`).

## Data flow

```
Failed CI run
      |
      v
  Collector ---> failure context (logs, diff, relevant files)
      |
      v
  Diagnoser ---> root-cause hypothesis + confidence
      |
      v
   Patcher  ---> candidate diff
      |
      v
  Validator ---> pass/fail + regression flag   (isolated Docker sandbox)
      |
      v
 Gatekeeper ---> propose PR   |   escalate to human
      |
      v
 Orchestrator logs the full trace (becomes evaluation data)
```

## Safety constraints (apply to every component)

- No component merges to main. Output is always a PR or an escalation report.
- No generated code executes outside the Validator's isolated Docker sandbox.
- Only the Orchestrator has authority to open a PR; individual agents don't call the GitHub
  API directly (noted here as a design constraint — GitHub integration isn't built yet).

## Current status

Collector, Diagnoser, Patcher, Validator, Gatekeeper, and Orchestrator are all unimplemented.
Phase 0 (current) is only the surrounding service skeleton (FastAPI app, `/health`, config,
CI). See `README.md` for status and `docs/decisions.md` for the phased build plan.
