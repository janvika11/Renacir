# Evaluation Plan

## Conditions compared

On the same curated benchmark (see Benchmark strategy):

1. **Traditional CI reporting** — failure surfaced, no repair attempt. Control condition.
2. **Single-agent repair** — one LLM call from logs directly to a diff, no validation step.
3. **Multi-agent repair, ungated** — full pipeline (Collector→Diagnoser→Patcher→Validator);
   every generated patch becomes a proposed PR regardless of confidence.
4. **Multi-agent repair, gated** — same pipeline, Gatekeeper decides propose-vs-escalate.

## Baselines (for the Gatekeeper specifically)

Per `docs/decisions.md`, the gate is built and evaluated baseline-first:

1. Validation-only rule — propose iff the Validator passes with no regressions (no confidence
   estimation at all).
2. Learned confidence model — e.g. logistic regression over Diagnoser confidence, patch
   features, and Validator outcome, evaluated via held-out risk-coverage curves.
3. Threshold-based selective prediction — a Chow's-rule-style threshold calibrated on
   held-out data, no formal guarantee claimed.
4. Conformal-style calibration (jackknife+/CV+) — investigated only after (1)–(3) exist, and
   only if the exchangeability check below doesn't rule it out.

## Metrics

Formal definitions, operational meaning, relevance, and limitations for every metric below
are frozen in `docs/research_protocol.md` §10 — this section is a summary, not the
authoritative source.

- **Repair effectiveness:** repair success rate (patched code passes held-out tests, no
  regressions).
- **Gate quality:** false-PR rate, escalation precision/recall, calibration curves /
  coverage-vs-risk tradeoffs.
- **Cost:** LLM cost and wall-clock latency per repair attempt, per condition.
- **Comparative:** all metrics reported per condition (1–4) so each pipeline stage's marginal
  value (validation, gating) is visible, not just the final system's numbers in isolation.

## Benchmark strategy

- ~30–50 curated cases, Python + PyTest, assertion failures and import/dependency errors only
  (per `PROJECT_SPEC.md`).
- Source: hand-crafted/injected bugs in small pytest repos with a known ground-truth fix — a
  pre-existing corpus at this exact scope doesn't appear to exist (see `docs/decisions.md`). A
  filtered pytest-only subset of an existing benchmark (e.g. SWE-bench-lite) is a possible
  supplement, evaluated for fit before use, not assumed.
- Each case records failing repo state, failing test output, a **reference repair** (not
  necessarily the unique correct fix — see `docs/research_protocol.md` §7), repo/source-group
  identity (needed for the exchangeability check below), source (synthetic vs. real), and its
  repository-level split role — schema implemented in `benchmarks/manifest.json` as of Phase
  2A; see `docs/benchmark_schema.md` for the full field reference. Independent
  held-out/differential correctness checks remain per-case optional, not yet constructed for
  either current fixture.
- Curated starting in Phase 1, not after the pipeline is built — benchmark feasibility is
  treated as the primary project risk.

## Exchangeability check (required before any coverage-guarantee claim)

Cases from the same repository may share style/bug patterns and are not automatically
exchangeable. Before using any conformal-style method or reporting a formal coverage number:

- Check whether the benchmark is repo-clustered.
- If so, use a repo-stratified or leave-one-repo-out split, not a random split.
- If exchangeability can't be established, report the empirical risk-coverage curve and say
  so explicitly, rather than stating a formal guarantee.

## Planned experiments

1. Run conditions 1–4 on the full benchmark; report per-condition metrics above.
2. For the Gatekeeper: compare baselines (1)–(3) via risk-coverage curves; only then evaluate
   whether (4) is appropriate given the exchangeability check.
3. Ablation: compare at least two distinct gating strategies head-to-head on identical inputs.
4. Report honestly if the gate does not calibrate well, or if conformal assumptions don't
   hold for this benchmark — a legitimate, reportable finding, not a failure to hide.

## Out of scope for v1 evaluation

- Comparing raw repair rate against SWE-bench-leaderboard-style agents — those solve a
  broader problem (arbitrary GitHub issues) at a different scale; related work, not a
  competitive baseline.
- Human-subject studies of developer trust in the escalation reports — a reasonable future
  extension, not attempted here.
