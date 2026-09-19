# Architecture

Renacir's repair pipeline exists to produce (patch, correctness) pairs for studying the
confidence gate — it is the testbed, not the end goal (see `PROJECT_SPEC.md`).

## Components

**Collector** — implemented, Phase 3 (`src/renacir/collector/`).
Input: a benchmark/reconstructed case id (`CollectorInput`). Live GitHub Actions ingestion
(repo, commit, workflow logs) is a later integration phase, not built yet — this phase
consumes cases via the existing `renacir.benchmark` staging/execution infrastructure only.
Output: `CollectorOutput` — execution evidence (stdout/stderr/exit code), a deterministically
parsed failure (error type/message, traceback frames, summary — no LLM), and a deterministic,
bounded selection of relevant source files (the failing test file plus its direct local
imports, or whatever the traceback itself references). See `docs/collector.md` for the full
contract, context-selection rules, and information-boundary guarantees, including the
retrospective-test-overlay handling for reconstructed real cases.

**Diagnoser** — offline core implemented, Phase 4B (`src/renacir/diagnoser/`).
Input: an explicit `DiagnoserInput` allowlist built from the Collector's output (never
`CollectorOutput` itself), excluding benchmark taxonomy metadata (category) and everything
`docs/collector.md` already excludes.
Output: a structured `Diagnosis` — root-cause summary, suspected files/symbols, a concise
reasoning summary, a self-reported and explicitly-uncalibrated `diagnosis_confidence`, and a
first-class `insufficient_context` flag. No patch, diff, or repair instruction of any kind.
Implementation: a single provider call in v1 — no multi-step agent loop, no retry. **No LLM
SDK is installed and no real model call has been made yet** — the core is exercised only
through a `FakeProvider`. See `docs/diagnoser.md` for the full contract and confidence
semantics.

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

Collector is implemented (Phase 3), scoped to benchmark/reconstructed cases only — see above
and `docs/collector.md`. Diagnoser's provider-independent core is implemented (Phase 4B) but
has made zero real LLM calls — no SDK is installed, no provider adapter beyond the offline
`FakeProvider` exists, and no diagnosis experiment has been run. Patcher, Validator,
Gatekeeper, and Orchestrator are all still unimplemented. No LLM SDK and no GitHub API
integration exist anywhere in the codebase yet. See `README.md` for status and
`docs/decisions.md` for the phased build plan.
