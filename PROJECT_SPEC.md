# Project Specification

## Research question

Primary: does a confidence-gated multi-agent repair system produce a better trade-off between
correct-patch coverage and false-positive proposals than (a) no repair at all, (b) ungated
single-agent repair, and (c) ungated multi-agent repair — and can the gate itself be shown to
be well-calibrated?

Secondary:
- Does decomposing repair into specialized stages (diagnose → patch → validate) outperform a
  single end-to-end LLM call, holding the underlying model constant?
- Can a lightweight, empirically-grounded confidence signal reliably distinguish "safe to
  propose" from "needs a human," and under what conditions (if any) does a formal statistical
  guarantee (e.g. conformal calibration) apply to that signal?

## Objectives

1. Build a minimal, safety-constrained repair pipeline for a narrow, well-defined class of
   Python/PyTest CI failures.
2. Build a small, honestly-labeled benchmark of reproducible failures with known fixes,
   including — for a stated subset — an independent correctness check beyond the
   originally-failing test (see `docs/research_protocol.md` §7).
3. Design and evaluate a confidence gate that decides whether to propose a patch as a PR or
   escalate to a human.
4. Compare four conditions (traditional reporting, single-agent, multi-agent ungated,
   multi-agent gated) on that benchmark.
5. Report the gate's calibration behavior honestly, including negative or mixed results.

## Scope (v1)

- Python + PyTest + GitHub Actions only.
- Failure classes: assertion failures and import/dependency errors only.
- Repos: small-to-medium pure-Python libraries, no compiled extensions, no external services
  required to run the test suite.
- Benchmark size: ~30–50 curated cases.
- Output: an opened PR with the patch and evidence, or an escalation report — never an
  automatic merge.

## Non-goals (explicit)

- Not a general-purpose coding agent — no open-ended feature work, no multi-file refactors.
- Not for flaky, non-deterministic, or infra/network-dependent failures.
- Not multi-language or multi-CI-system in v1.
- Not a new conformal-prediction method — Renacir applies and stress-tests existing
  selective-prediction/calibration techniques in a new setting, it does not claim new theory.
- Not attempting to beat state-of-the-art repair agents (SWE-agent, AutoCodeRover, Agentless)
  on raw repair rate — those solve a broader problem and are related work, not a competitor.

## Assumptions

- A ~30–50 case benchmark is small; statistical claims about the gate are scoped accordingly
  (see `EVALUATION_PLAN.md` and `docs/decisions.md`).
- Code-repair cases are not assumed exchangeable across repositories — this is checked, not
  assumed, before any coverage-guarantee claim is made.
- The underlying LLM(s) used for diagnosis/patch generation are a fixed, external component;
  Renacir does not fine-tune a model.
- An isolated, network-disabled, resource-limited Docker sandbox is assumed sufficient for
  safely running LLM-generated code during validation.

## Expected contributions

- An empirical study of whether a small, execution-verified benchmark supports honest
  selective-prediction/calibration claims for autonomous code repair, and where those claims
  break down.
- A working, safety-constrained reference pipeline — itself a means to an end, not the
  contribution — that produces the (patch, correctness) pairs the study needs.
- A head-to-head comparison, on the same benchmark, of a baseline threshold gate against a
  calibration-aware alternative, reported with explicit statements of the assumptions each
  relies on.

We do not claim to be first to apply selective prediction or conformal-style calibration to
LLM outputs — see `docs/decisions.md`'s literature checkpoint for prior work. The contribution
is applying and honestly evaluating this approach specifically for execution-verified code
repair, at small-benchmark scale — not inventing new gating theory.
