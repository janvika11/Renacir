# Research Protocol

**Status: FROZEN — 2026-09-18.** Governs methodology before any of Collector, Diagnoser,
Patcher, Validator, Gatekeeper, or Orchestrator is implemented. Amendments require a new
dated entry in `docs/decisions.md`, not a silent edit here.

This document is the authoritative source for research-methodology questions referenced
more loosely elsewhere (`PROJECT_SPEC.md`, `ARCHITECTURE.md`, `EVALUATION_PLAN.md`). Where
this document and those disagree, this document governs for methodology; those documents
govern for scope/architecture as stated in them.

A Phase 1.6 literature checkpoint (`docs/literature_review.md`, 2026-09-18) has since
verified specific methodological claims made or left open below; sections it touched are
marked inline with a pointer to that document. The checkpoint resolved a small number of
narrow questions (see "Unresolved methodological questions" below) and left the rest exactly
as open as before — see `docs/decisions.md` for the dated change log.

Several methodological decisions are deliberately **not** made here — see the "Unresolved
methodological questions" and "Literature questions to answer" sections at the end. Treating
an item as unresolved is itself a decision recorded by this freeze; it is not an oversight.

## 1. Primary research question

Can validation-derived confidence signals support selective prediction for LLM-generated
code repairs, allowing Renacir to retain useful automated repair coverage while reducing
incorrect repair proposals through abstention?

## 2. Secondary research questions

- Does decomposing repair into specialized stages (diagnose → patch → validate) outperform
  a single end-to-end LLM call, holding the underlying model constant? (from `PROJECT_SPEC.md`)
- Does a *validation-derived* signal (Validator pass/fail + regression flag) alone suffice as
  a gate input, or does adding LLM self-reported confidence (Diagnoser/Patcher stated
  confidence) measurably improve the risk-coverage trade-off over validation alone? This
  operationalizes the word "validation-derived" in the primary RQ as a testable contrast,
  not an assumption — LLM self-reported confidence is NOT assumed calibrated for code (see
  §16, §21).
- Under what conditions, if any, does a formal statistical coverage guarantee (e.g.
  conformal-style calibration) apply to the gate's signal? (from `PROJECT_SPEC.md`)

## 3. Target population and scope

Inherits `PROJECT_SPEC.md` §Scope exactly:
- Python 3.11+, PyTest, GitHub Actions only.
- Failure classes: assertion failures and import/dependency errors only.
- Small-to-medium pure-Python repos, no compiled extensions, no external services required
  to run the test suite.

**Explicitly excluded**: other languages, deployment/infra failures, Kubernetes/cloud
failures, production incidents, general vulnerability remediation, auto-merge, IDE
integration, general-purpose autonomous coding.

Any claim in the eventual write-up must be scoped to this population by name. "Renacir
repairs CI failures" is not a valid sentence in the final report; "Renacir repairs
assertion/import failures in small pure-Python PyTest projects" is.

## 4. Unit of evaluation

Three distinct units, not to be conflated:

- **Case**: a fixed (repository snapshot, failing test node, gold patch) tuple — the static
  benchmark entity, as already implemented in `benchmarks/manifest.json`.
- **Attempt**: one Patcher invocation producing one candidate diff for a case, under one
  experimental condition (§9).
- **Run**: one full pipeline execution of a case under a condition, which may itself retry
  internally (Diagnoser/Patcher retry budget — `ARCHITECTURE.md` already lists "retry count"
  as a Gatekeeper input feature, implying retries exist; this protocol requires the retry
  policy to be fixed and logged, §15).

Coverage/risk statistics (§10) are computed **per case**, not per attempt/run, after
aggregating repeated runs (§14) — treating repeated stochastic runs of the same case as
independent observations would pseudo-replicate and violate the independence assumptions
selective-prediction and any conformal-style analysis need.

## 5. Benchmark inclusion criteria

A case is included only if:
1. Pure Python 3.11+, runnable via `pytest` with no network access and no external services.
2. The failure is deterministic: identical outcome across ≥5 consecutive reruns with no
   environment changes.
3. The failure is attributable to exactly one of the two v1 categories (assertion, import),
   per the rubric in §6/§7.
4. A single, minimal, author-agreed **gold patch** exists: applying it makes the failing
   test(s) pass with zero regressions on the rest of the suite.
5. Repository is small: ≤5,000 LOC / ≤50 files (an explicit, arbitrary, stated ceiling — not
   derived from data — chosen to bound Diagnoser context size and Validator sandbox runtime).
6. No compiled extensions, no GPU, no credentials required.
7. If sourced from a real repository: license permits inclusion and redistribution for
   research/study use.
8. Provenance is recorded (`"source": "synthetic" | "real"` in `case.json`).

**Inclusion is determined solely by the declared task population and scope (§3),
independent of Renacir's own implementation.** Whether the gold patch happens to touch files
a future Collector would or wouldn't surface is **not** an inclusion criterion. If Collector,
once built, fails to retrieve a file necessary for an otherwise in-scope repair, that is a
**pipeline/retrieval failure** to be measured and attributed to the Collector stage — not
evidence the benchmark case was invalid. A concrete retrieval-completeness diagnostic
(whether Collector's relevant-file set actually contains every file the gold patch touches)
is deferred until Collector exists — noted here as a forward reference, not specified now
(see unresolved item 12).

## 6. Benchmark exclusion criteria

- Flaky tests (time-based, network-based, unseeded randomness, order-dependent).
- Non-pytest test runners or non-Python code.
- Failures requiring infra/deployment/Kubernetes/cloud state.
- Failures whose only fix requires multi-file refactors or architecture-level changes, per
  `PROJECT_SPEC.md`'s stated non-goals ("not a general-purpose coding agent... no multi-file
  refactors") — scoped against the declared task population (§3), independent of what any
  implementation of Collector happens to retrieve (§5).
- Failures with multiple materially different, equally-defensible fixes and no principled
  way to designate one as canonical gold (ambiguous-ground-truth cases are logged separately
  in a "reviewed and rejected" list, not silently included as single-answer cases).
- "Fixes" that consist of installing/removing/pinning a dependency rather than editing code
  (out of scope — Patcher edits code, not environments).
- Near-duplicate cases (same root-cause pattern + same repo) beyond a declared cap per
  repo/pattern (protects the repo-clustering/exchangeability concern already flagged in
  `EVALUATION_PLAN.md`).
- Cases whose test is trivially satisfiable by near-arbitrary code (a triviality check —
  e.g. does a deliberately-wrong dummy patch also pass the test? If so, reject or strengthen
  the test before inclusion).

## 7. Correctness taxonomy — the "tests pass" vs "semantically correct" distinction

Every generated candidate patch, once produced by the pipeline (this happens **before** the
Gatekeeper decision — a candidate always exists, per `ARCHITECTURE.md`'s data flow, so
correctness tiers can be computed for a case regardless of whether the gate would abstain),
is classified into exactly one tier:

### 7.1 Correct repair (tier 1)
All of the following hold:
(a) The originally-failing test(s) pass after applying the diff.
(b) No previously-passing test in the full suite now fails (no regression, §7.4).
(c) At least one of the following **independent** correctness checks also passes:
   - A **held-out test**, authored independently of the fix attempt, targeting the same
     code path/bug, not visible to Diagnoser/Patcher at generation time (kept outside the
     Collector-relevant file scope, alongside the gold patch — see leakage rule §20).
   - **Differential/equivalence testing against the gold patch**: run both the candidate-
     patched and gold-patched versions against a shared set of generated inputs (e.g. via
     property-based testing where the function signature admits it) and require output
     agreement across N inputs. This raises confidence of semantic equivalence; it does
     not prove it. Literature-supported (`docs/literature_review.md` §2, §9): SWT-Bench
     (Mündler et al., NeurIPS 2024, full-read) validates generated tests via differential
     fail→pass execution against the gold patch rather than a held-out set, and reports
     generated tests can still pass an incorrect patch — direct precedent for treating this
     check as raising confidence, not proving correctness. PatchDiff (Wang, Pradel & Liu,
     arXiv 2503.15223, full-read) is a concrete existing technique for exactly this kind of
     differential testing, and its own manual audit found most behavioral divergences from
     an oracle patch were of *uncertain* correctness (66.2% of a sampled set), not
     automatically incorrect — direct empirical support for treating divergence as
     inconclusive by default, not as a failure.
   - For import/dependency cases specifically: static verification that the corrected
     import resolves to a symbol whose signature is call-site-compatible with actual usage
     — a comparatively strong, cheap, near-formal check available for this one failure
     class.

**Correctness does not require syntactic or structural similarity to the gold patch.** The
differential/equivalence check above tests *behavioral* agreement on shared generated
inputs, not diff or AST similarity — a candidate patch that fixes the bug via a different
code path, different variable names, or a different but valid strategy is tier-1 correct if
it satisfies (a), (b), and any one of the (c) checks. Multiple semantically valid repairs
may exist for a given case; the gold patch (`expected/fix.patch`) is a fixed *behavioral
reference* used to construct checks like differential testing and to define "no regression,"
not a canonical implementation the candidate must resemble. This taxonomy is preserved as-is
by the literature checkpoint, not replaced by it: Qi et al. (ISSTA 2015, full-read,
`docs/literature_review.md` §2) independently established the plausible-vs-correct
distinction this section is built on, and PatchDiff's own documented example (a divergent-
but-defensible matplotlib patch) is read as direct support for the no-syntactic-similarity
rule specifically — Renacir does not adopt PatchDiff's own correctness taxonomy or thresholds
in its place.

### 7.2 Plausible-but-not-established-correct repair (tier 2)
(a) and (b) above hold, but (c) does not — no held-out test exists for that case, the
differential check is inconclusive, or no independent check is available. **This is
expected to be the common outcome for many v1 cases**, given that authoring held-out tests
for every case is itself significant work not yet budgeted (see unresolved item 2). This
tier exists specifically so "test passes" is never silently reported as "correct."

### 7.3 Incorrect repair
The originally-failing test still fails, OR a regression occurs, OR (when evaluable) the
independent check fails outright, OR the diff does not apply/does not parse.

### 7.4 Regression (component of the tiers above, also tracked separately)
Any previously-passing test in the full suite that fails after the patch is applied. Bounded
by the existing suite's own coverage — a regression not covered by any existing test is
invisible to this check, a limitation to be stated, not hidden (§17).

**Hard rule**: any reported "repair success rate" must state which tier(s) it counts.
"Repair success rate (tier 1 only)" and "repair/plausible rate (tier 1 ∪ tier 2)" are always
reported side by side, never collapsed into one unlabeled number (§10.9).

## 8. Definition of abstention / escalation

**Abstention** is the Gatekeeper's decision output `propose | abstain`, made *after* a
candidate patch and its correctness tier already exist internally — abstention withholds
disclosure of the patch as a PR, it does not prevent generation.

**Escalation** is the resulting user-facing artifact when the decision is `abstain`: an
escalation report containing the evidence trail behind the decision (per `ARCHITECTURE.md`).
Abstention and escalation refer to the same event from two angles (decision vs. output
artifact) and are not independently measured.

A case can land in any of four cells: {propose, abstain} × {tier-1-correct, not-tier-1}.
All four are tracked; §10 metrics are functions of this 2×2 (or, with tier 2 reported
separately, 2×3) table.

## 9. Baselines vs. conditions (two different axes — kept explicitly separate)

`EVALUATION_PLAN.md` uses "baseline" for two different things; this protocol disambiguates:

**System-level conditions** (compared on the same benchmark, per `EVALUATION_PLAN.md`):
1. Traditional CI reporting (control, no repair attempt).
2. Single-agent repair, no validation.
3. Multi-agent repair, ungated (every patch proposed regardless of confidence).
4. Multi-agent repair, gated.

**Gatekeeper baselines** (compared *within* condition 4, all candidates for "the gate," none
pre-selected):
- B0. **Always propose** / **always abstain** — degenerate reference lines every
  risk-coverage curve must be compared against.
- B1. **Validation-only rule** — propose iff Validator passes with no regression. This is
  the mandatory transparent baseline: no result may report a "more sophisticated" gate
  without B1 reported alongside it on the same cases.
- B2. Learned confidence model (logistic regression / GBT over diagnosis confidence, patch
  characteristics, validator outcome).
- B3. Threshold-based selective prediction (Chow's-rule-style), calibrated via held-out
  risk-coverage analysis, no formal guarantee claimed.
- B4. **Conformal-style calibration** — a *candidate class* of methods (e.g. split-conformal,
  jackknife+, CV+) to investigate, not a chosen method. Investigated only after B1–B3 exist,
  and only if the exchangeability check (§21, `EVALUATION_PLAN.md`) and the literature
  review support it for this dataset's repository-clustering structure and sample size. No
  specific technique within this class is preferred or assumed here.

  **Literature checkpoint result** (`docs/literature_review.md` §5, §10): none of the
  conformal-prediction families examined so far has literature-established applicability to
  Renacir's specific combination of repository-grouped observations, small sample size, and
  stochastic repair outputs. Specifically, and by direct reading, not inference from titles:
  jackknife+/CV+ (Barber et al., Annals of Statistics 2021, full-read) explicitly states its
  guarantees likely fail under correlated within-group observations; "conformal prediction
  beyond exchangeability" (Barber et al., Annals of Statistics 2023, full-read) and "split
  conformal prediction and non-exchangeable data" (Oliveira et al., JMLR 2024, content
  confirmed) both target *temporal* drift specifically, not discrete-group dependence, despite
  superficially relevant framing; class-conditional/"clustered" conformal prediction (Ding et
  al., NeurIPS 2023, metadata-verified) clusters *prediction classes* with too few calibration
  examples, a different statistical problem from source-repository dependence that happens to
  share the word "clustered"; Mondrian conformal prediction (Vovk et al., 2003, unpublished
  technical report) is the structurally closest match but its own known failure mode — too
  few examples per group — is the likely regime for most of Renacir's repositories.

  **This is a negative finding, not a gap in search effort, and it does not mean conformal
  prediction is invalid in general** — only that its applicability to Renacir specifically
  remains unsupported and unresolved. None of jackknife+, CV+, Mondrian, class-conditional
  conformal prediction, or a beyond-exchangeability method is selected by this freeze. All
  remain candidates for reconsideration once real repository/case counts exist.

## 10. Primary and secondary evaluation metrics

There is **no single scalar primary metric** — the RQ is inherently about a trade-off, so
the primary evaluation artifact is the **risk-coverage curve** (§10.3), with coverage and
selective risk (§10.1–10.2) as its two components.

Notation: n cases, φ(case) ∈ {propose, abstain} the gate decision, c(case) ∈ {0,1} the
binary correctness indicator (1 = tier-1 correct; a lenient variant with tier-1 ∪ tier-2 = 1
is reported as a labeled sensitivity check, never silently substituted, §7.3/§22).

### 10.1 Coverage (primary)
`C(φ) = (1/n) Σ 1[φ(case_i) = propose]`
*Relevance:* operationalizes "retain useful automated repair coverage" from the RQ.
*Better:* higher, **only meaningful jointly with risk** — a system proposing everything has
C=1 regardless of quality.
*Limitation:* says nothing about quality alone; never reported unpaired from §10.2.

### 10.2 Selective risk (primary)
`R(φ) = [Σ_i 1[φ=propose]·(1-c_i)] / [Σ_i 1[φ=propose]]` (undefined at C=0, reported as N/A)
*Relevance:* error rate among what's actually proposed — operationalizes "reducing incorrect
repair proposals." This is the standard selective-prediction risk (Geifman & El-Yaniv 2017,
already vetted in `docs/decisions.md`).
*Better:* lower.
*Limitation:* at n≈30–50 with low coverage, the denominator can be very small — empirical
selective risk is then extremely high-variance. Must always be reported with an exact
(Clopper-Pearson) binomial confidence interval, not a bare point estimate.

### 10.3 Risk-coverage curve (primary artifact)
R(φ_t) plotted against C(φ_t) as the gate's decision threshold t sweeps its range.
*Relevance:* the full trade-off the RQ asks about; matches the Geifman & El-Yaniv framework
already adopted.
*Better:* a curve that dominates (lower risk at every coverage level) another.
*Limitation:* at n≈30–50, achievable coverage levels are quantized in ~1/n steps (already
noted in `docs/decisions.md`'s Gatekeeper-design entry) — the curve is a step function, not
smooth, and must be presented as such.

### 10.4 Area under the risk-coverage curve (AURC) — conditionally justified, secondary only
`AURC(φ) = ∫₀¹ R(φ_t) dC` (discretized sum in practice).
*Relevance:* single-number summary for headline comparison tables.
*Justification decision:* given the coarse step-function curve at this n (§10.3), AURC is
included **only as a secondary summary statistic reported alongside the full curve**, never
in place of it, and never as the sole basis for a comparative claim. This status is
unchanged by the literature checkpoint (`docs/literature_review.md` §7, §10): Zhou, Van
Landeghem, Popordanoska & Blaschko (ICML 2025, arXiv 2410.15361 — metadata-verified, not
full-read) establish finite-sample AURC plug-in estimators are consistent, converging at
rate O(√(ln(n)/n)) — real and on-point, but that rate is loose at n≈30–50 (illustratively,
√(ln(30)/30) ≈ 0.34). This keeps AURC secondary, as already decided; it neither promotes AURC
to primary nor removes it, and it does not supply a usable finite-sample uncertainty figure
for a reported AURC number at Renacir's scale — that remains unresolved.
*Limitation:* a scalar necessarily discards the shape of the trade-off, which is the more
informative object at small n.

### 10.5 False proposal rate — disambiguated (two readings, both defined, one primary)
`EVALUATION_PLAN.md` uses this term without a formula. Two non-equivalent readings exist:
- **Conditional** (= selective risk, §10.2): `P(incorrect | propose)`.
- **Unconditional**: `(1/n) Σ 1[φ=propose ∧ incorrect]` — rate over the *whole* benchmark.
*Decision:* selective risk (conditional) is the primary definition, matching standard
selective-prediction terminology; unconditional rate reported as a secondary, clearly
labeled number.

### 10.6 Abstention / escalation rate
`= 1 − C(φ)`. Same information as coverage, different audience framing (what a human
reviewer experiences). Same limitation as §10.1 — never reported unpaired from risk.

### 10.7 Calibration / reliability analysis
For any confidence-like score s(case) ∈ [0,1] a candidate gate emits, bin cases by s and
compare mean predicted score to empirical accuracy per bin (reliability diagram).
*Relevance:* this is the literal operational meaning of "confidence" in this project:
confidence means an empirical estimate of `P(tier-1 correct | signal)`, and calibration
means that estimate matches observed frequency — nothing more, nothing metaphysical.
*Better:* points closer to the diagonal.
*Limitation:* standard multi-bin reliability diagrams need enough samples per bin to be
meaningful; at n≈30–50 total, a 10-bin diagram is very likely underpowered — confirmed by
the literature checkpoint (see §10.8 below; "Literature questions — checkpoint status" item
1 in `docs/research_protocol.md`'s closing section, and `docs/literature_review.md` §4).
Exact binning strategy for a reliability diagram at this n remains open.

### 10.8 Calibration-summary methodology (ECE, Brier score, or alternatives) — partially resolved

Candidates include Expected Calibration Error (`ECE = Σ_b (|B_b|/n)|acc(B_b) − conf(B_b)|`),
the Brier score (`(1/n)Σ(s_i − c_i)²`, a proper scoring rule requiring no binning), and other
small-sample-appropriate alternatives (e.g. smoothed/kernel reliability curves).

Calibration and ranking quality are separate properties: risk-coverage analysis (§10.3) only
requires the confidence score to rank cases well, not to be probabilistically calibrated —
so whichever calibration summary is chosen, it is a secondary diagnostic, never a substitute
for the risk-coverage curve.

**Decided (literature checkpoint, `docs/literature_review.md` §4, §9): naive equal-width
histogram-binning ECE is ruled out as the primary scalar calibration summary at Renacir's
expected n≈30–50.** Kumar, Liang & Ma (NeurIPS 2019, full-read) show histogram-binning
calibration-error estimation requires O(B/ε²) samples — concretely ~4,000 samples for B=10
bins at ε=0.05 — one to two orders of magnitude above Renacir's scale. Roelofs et al.
(AISTATS 2022, full-read) independently show reliably detecting 2% miscalibration requires
over 10,000 samples, and below 500 samples only miscalibration exceeding ~10% is reliably
detectable at all. Both findings are full-text-verified, not abstract-level extrapolations.

**Still unresolved**: whether the Brier score alone is sufficient at this n, or whether no
scalar calibration summary should be reported at all (only the risk-coverage curve and a
reliability diagram); and how to represent uncertainty around whatever calibration estimate
is eventually reported. Neither question is settled by the ECE finding above, and neither is
decided here.

### 10.9 Repair success rate / plausible repair rate (tiered — never collapsed, §7)
`SuccessRate = (1/n)Σ 1[tier=1]`, `PlausibleRate = (1/n)Σ 1[tier∈{1,2}]`, always reported
as a pair, per case attempted (independent of gate decision).
*Relevance:* separates "is the underlying repair pipeline good" from "is the gate good."
*Better:* higher, for either, holding the other and regression rate fixed.
*Limitation:* reporting `PlausibleRate` alone would silently reintroduce the "tests pass ⇒
correct" conflation this protocol exists to prevent — the pairing rule is a hard requirement.

### 10.10 Regression rate
`(1/n) Σ 1[regression occurred]` (§7.4). *Relevance:* direct safety metric, especially given
"never auto-merge" is the system's only other safety net. *Better:* lower, ideally 0 among
*proposed* patches specifically. *Limitation:* bounded by existing suite coverage — a real,
statable ceiling on what this metric can detect.

### 10.11 Diagnosis accuracy — metric provisional, not frozen

**Candidate** operational proxy: line-level fault-localization accuracy — whether the
Diagnoser's hypothesis cites the actual buggy line(s), knowable from `case.json`'s
`root_cause` field (synthetic cases) or the gold patch's changed lines (real cases).
Proposed as a candidate specifically because it is objective and checkable, unlike free-text
causal-narrative matching, which needs a subjective rubric not yet drafted.

This is **not the final diagnosis-accuracy metric**. The Phase 1.6 literature checkpoint
(`docs/literature_review.md` §7, §10; "Literature questions — checkpoint status" item 7)
confirmed Top-N/line-level accuracy is standard APR practice, supporting this as a reasonable
candidate — but exact granularity (line- vs. function-level) and partial-credit scoring
remain open and are not decided by that confirmation.

### 10.12 Latency
Wall-clock time per pipeline stage and end-to-end, reported as median + IQR (not mean alone,
given expected right-skew from retries/timeouts).
*Relevance:* `EVALUATION_PLAN.md`'s "Cost" metric category; informs eventual real-world
viability.
*Better:* lower, holding correctness/coverage fixed — report as a pairing (e.g. cost per
correct repair), not standalone.
*Limitation:* highly infra-dependent (API rate limits, sandbox cold start, local load) — must
be reported with the exact hardware/network conditions logged (§15) and flagged as not
necessarily representative of production.

### 10.13 Token / API cost
Input+output tokens and computed $ cost per stage and end-to-end, at a logged pricing
snapshot date.
*Relevance:* same Cost category; also informs the decomposition secondary RQ (more LLM calls
= more cost — is the accuracy gain worth it?).
*Better:* lower, holding correctness fixed — report as cost-per-correct-repair.
*Limitation:* pricing changes over time/providers; numbers are uninterpretable later without
the exact model version + pricing-date logged (§15).

### 10.14 Secondary composite metrics
- Escalation recall = `P(abstain | tier≠1)` — of truly-bad repairs, how many were caught.
- Escalation precision = `P(tier≠1 | abstain)` — of escalated cases, how many were actually
  bad (vs. the gate being needlessly conservative).
  (Both formalize `EVALUATION_PLAN.md`'s undefined "escalation precision/recall" bullet.)
- Cost per correct repair = total cost ÷ count of tier-1-correct proposals.
- Failed/timed-out run rate (§14) — tracked as its own category, never silently folded into
  "incorrect."

## 11. Dataset construction methodology

Two sourcing tracks:
- **(a) Synthetic**: hand-injected bugs in small authored pure-Python repos, packaged exactly
  as the 2 current fixtures (`case.json` + manifest entry + `reference/fix.patch`).
- **(b) Real**: mined historical bugfix commits from open-source PyTest repos — a commit `C`
  qualifies if checking out `C`'s parent reproducibly fails the test(s) `C` fixes, `C`'s own
  diff serves as the reference repair (not the unique correct fix — see §7), and the case
  otherwise meets §5/§6. Requires manual triage per candidate (labor-intensive; not
  automatable beyond initial candidate search).

**Schema implemented as of Phase 2A** (`docs/benchmark_schema.md`, `docs/decisions.md`):
`manifest.json` per case now carries `execution` (runtime/environment metadata, case-specific
— not assumed to match Renacir's own Python 3.11+ requirement), `source` (`type`:
`"synthetic" | "real"`, plus `source_group_id` for repo/template-level grouping — see §13),
and `curation` (`status`, `fold` placeholder, `contamination_risk`) blocks, superseding this
section's earlier, simpler four-field sketch. Both tracks use identical downstream tooling
regardless of provenance. Rejected real-world candidates are recorded separately in
`benchmarks/candidates.json`, not forced into the executable manifest.

**Target real:synthetic ratio is not fixed here** — see unresolved item 1.

## 12. Synthetic-vs-real-case reporting policy

- Every headline metric (§10) is reported **both pooled and broken out by source**, whenever
  each subgroup has enough cases to not be pure noise (minimum n per subgroup TBD, unresolved
  item 5).
- **Hard rule**: no claim may say "Renacir repairs X% of real-world CI failures" unless
  backed by the real-case subset specifically. The current 2-case benchmark is 100%
  synthetic/infrastructure-validation — no real-world performance claim is currently
  supportable, and none should be implied.
- Synthetic cases remain useful indefinitely for controlled ablations (author knows the true
  root cause, enabling cleaner diagnosis-accuracy measurement, §10.11) — not deprecated once
  real cases exist, just always labeled.

## 13. Repository-level development / calibration / test separation

- **Hard requirement**: split at the repository level, not the case level — no repository's
  cases may be split across roles (a repo assigned to `test` contributes no cases to
  `calibration` or `development`, and vice versa). This is fixed and non-negotiable,
  independent of the exact scheme chosen below.
- Three roles: **development** (free prompt iteration), **calibration** (fit/threshold the
  Gatekeeper only — never used for prompt engineering), **test** (touched only for final
  reported numbers; no iteration against test-fold feedback — computed via a single script
  run at the end, not re-run after inspecting results).
- **The exact splitting scheme is unresolved** — candidates include a fixed 3-way split,
  leave-one-repo-out (LORO) cross-validation, or grouped k-fold CV. Which is appropriate
  depends on the final repository count and cases-per-repository, neither of which is known
  yet (unresolved item 4). A fixed split risks an uninformatively small test fold at this
  project's likely scale; LORO/grouped-CV avoid that but have their own tradeoffs (e.g.
  computational cost, variance across folds) — deferred until real numbers are available.
- Whatever scheme is chosen, it must respect the hard requirement above and the
  repo-clustering/exchangeability concern already flagged in `EVALUATION_PLAN.md`.

## 14. Repeated-run policy for stochastic LLM outputs

- Sampling settings (temperature, top_p, etc.) fixed and logged per condition (§15).
- Each case is run K independent times per condition. **Neither K nor the per-case
  aggregation rule (e.g. majority vote vs. "any failure counts as failure") is fixed here**
  — both remain open, pending a cost/power tradeoff analysis and possibly literature
  guidance on aggregating repeated stochastic LLM samples (unresolved items 3, 10). Whatever
  aggregation rule is eventually chosen must be frozen and logged before data collection
  begins, and applied uniformly across conditions.
- Aggregation, once chosen, produces the **primary unit** fed into §10 statistics
  (respecting true n = number of cases); per-attempt pooled statistics (treating each of the
  K runs as separate) are reported only as a labeled diagnostic, never as the primary n,
  since they are non-independent within a case.
- **Failed/timed-out runs** (API error, sandbox crash, non-deterministic hang) are logged as
  a distinct outcome category — never silently dropped (survivorship bias toward easy cases)
  and never silently counted as "incorrect" (conflates infra failure with model failure).
  Failed-run rate is reported separately.

## 15. Model, prompt, configuration, token-cost, and latency logging requirements

One structured (JSON) record per pipeline run, containing at minimum:
- Model name, exact version/snapshot id, provider, API endpoint.
- Prompt template (versioned/hashed, git-tracked) **and** the fully rendered prompt actually
  sent — not just the template — for reproducibility.
- Sampling parameters (temperature, top_p, max_tokens, seed if supported).
- Timestamp, per-stage and end-to-end wall-clock latency.
- Input/output token counts per stage, plus cost computed at a logged pricing-snapshot date.
- Full raw output per stage (Diagnoser hypothesis, Patcher diff, Validator stdout/stderr,
  Gatekeeper decision + evidence trail).
- Case id, repo, condition, run index (for §14 repeated-run tracking).
- Git commit hash of **Renacir's own codebase** at run time — makes pipeline-version drift
  during a multi-week collection window traceable.

## 16. Statistical analysis plan

- All point estimates (coverage, selective risk, etc.) reported with confidence intervals:
  exact **Clopper-Pearson** for proportions (appropriate at small n, unlike normal
  approximation) — **but only where the independence assumption behind it is appropriate**.
  Clopper-Pearson does not itself account for repository clustering: if cases from the same
  repository are correlated, a Clopper-Pearson interval on the pooled case-level proportion
  will understate true uncertainty, for the same reason naive cluster-robust standard errors
  do (Cameron, Gelbach & Miller, 2008, metadata-verified: cluster-robust methods presume "a
  large number of clusters," with standard asymptotic tests over-rejecting under ~5–30).
  This is the same open problem as repository-clustered uncertainty generally, immediately
  below — Clopper-Pearson is a correct tool for the unclustered part of an estimate, not a
  solution to that problem.
- **Repository-clustered uncertainty remains unresolved** (`docs/literature_review.md` §7,
  §10). MacKinnon & Webb ("The Wild Bootstrap for Few (Treated) Clusters," Econometrics
  Journal 21(2), 2018, DOI 10.1111/ectj.12107 — metadata-verified, not full-read) is recorded
  here only as a **candidate lead**: it shows wild cluster bootstrap remains reliable with
  very few clusters, but in a cluster-robust *regression* (treatment-effect) setting. That
  setting has **not** been established as applicable to Renacir's proportion/paired-binary
  outcome setting — the small-cluster-count problem is analogous, the statistical machinery
  has not been shown to transfer. **Wild cluster bootstrap is not adopted by this freeze.**
  Plain cluster bootstrap (resampling at the repo level) remains the tentative placeholder
  for composite statistics like AURC, with the same unresolved caveat.
- Comparisons between conditions use **paired** analysis on the same case set where possible
  (e.g. McNemar's test for paired binary correct/not-correct outcomes between gated vs.
  ungated on identical cases) — far more powerful than unpaired tests at this n, since
  pairing removes case-difficulty variance.
- Any significance claim states the exact test, n, and effect size — never a bare p-value.
- **Primary/confirmatory comparisons are pre-registered in this document** before data
  collection (to be finalized once the unresolved items are settled) to prevent post-hoc
  multiple-comparison fishing (§19).
- Formal coverage-guarantee claims (conformal-style) remain gated behind the exchangeability
  check (`EVALUATION_PLAN.md`) and the literature checkpoint's finding (§9) that no examined
  conformal family currently has established applicability to Renacir's structure — this
  document does not pre-decide any conformal method will be used.

## 17. Threats to validity

- **Internal**: single-author case construction/triage risks unconscious bias toward
  cases that flatter the eventual gate; partially mitigated by rubric-based inclusion
  criteria (§5/§6) and real-case mining, not eliminated.
- **Construct**: "confidence" as measured here is specifically `P(tier-1-correct | signal)`
  — it does not capture broader PR-acceptability concerns (style, maintainability). The
  protocol only claims to measure correctness-related trust.
- **External**: the v1 population (§3) is narrow by design. No result generalizes beyond it;
  this must appear in every results claim, not a footnote.
- **Statistical conclusion**: small n is likely the single biggest limitation of the whole
  study — addressed by §16 but not eliminated. Foreground this, don't bury it.
- **Reactive/instrumentation**: risk of unconsciously tuning prompts after seeing test-fold
  failures — mitigated by the fold-discipline in §13, but requires actual procedural
  discipline (the "single script run at the end" rule) to hold in practice.

## 18. Experimental integrity checklist

| Risk | Mitigation | Detail |
|---|---|---|
| Repository-level leakage | Repo-level split, exact scheme TBD | §13 |
| Ground-truth patch leakage | Gold patches never in Collector/Diagnoser/Patcher context; automated assertion that Collector never reads `expected/` | §20 |
| Prompt tuning on test cases | Prompts frozen/hashed before any test-fold run; any change re-declares the fold spent | §15, §13 |
| Model/version changes mid-experiment | Model version + Renacir commit hash logged per run | §15 |
| Repeated stochastic runs | K and aggregation rule fixed and logged before data collection (both currently open) | §14 |
| Failed/timeout runs | Logged as distinct category, never dropped or mislabeled | §14 |
| Post-hoc metric selection | Metric set in §10 is final per run; anything computed after seeing results is labeled exploratory, never mixed with confirmatory results unlabeled | §16, §19 |
| Benchmark duplication | Dedup check at construction time; near-duplicates flagged in metadata even if included | §6 |

## 19. Data leakage risks and prevention

- Gold patches and held-out tests live outside the Collector's "relevant files" surface
  (already true structurally: `expected/` is not visible to the pipeline) — enforced by an
  automated test on the Collector's file-selection logic once built, not just convention.
- **Model provider training-data leakage / contamination**: for real mined cases from public
  GitHub repos, the LLM may have memorized the actual historical fix from pretraining —
  "correct repair" could reflect memorization, not repair capability. **Literature-confirmed**
  (`docs/literature_review.md` §6, §9) — this is a documented, converging concern across
  SWE-Bench Illusion (arXiv 2506.12286, full-read: no-repo-context diagnostic tasks score
  markedly higher on SWE-Bench-Verified than on external tasks, consistent across ten
  models), SWE-rebench (arXiv 2505.20411, full-read: DeepSeek-V3 scored 39.7% on SWE-bench
  Verified vs. 21.3% on contemporaneous fresh tasks — an 18.4-point gap on the same model),
  and SWE-bench's own internal check (full-read: a coarse pre/post-2023 temporal partition
  found "little difference," which the later, more targeted methods above contradict —
  showing coarse date-partitioning alone is an insufficient test).

  **Mitigation policy adopted for any real historical case Renacir sources:**
  - Record the issue/PR/fix commit date where available.
  - Record the evaluated model/version and its known training-cutoff date where available.
  - Flag (do not silently exclude) any case whose timing makes contamination plausible (e.g.
    fix predates the model's training cutoff by a wide margin, or the source repository is a
    popular, widely-discussed project).
  - Distinguish *direct evidence* of contamination (none is currently available for any
    Renacir case, and none of the cited papers claim direct evidence for their own cases
    either) from *diagnostic evidence consistent with memorization* (the accuracy-gap and
    no-context-performance patterns above) — never conflate the two in a report.
  - Never claim a specific case is *proven* uncontaminated. "Predates a model's stated
    training cutoff" is evidence, not proof, and is not sufficient by itself.
  - Do not assume a popular curated benchmark (e.g. BugsInPy) is safer than SWE-bench merely
    because it differs from SWE-bench in language scope or size — no source checked BugsInPy
    for contamination, and its status as a well-known 2020 academic benchmark plausibly puts
    it in the same training-data-representation risk class, not a lower one.

## 20. What conclusions this experiment could support

- Whether, on this specific benchmark drawn from the stated narrow population, a
  validation-derived gate changes the coverage/risk trade-off relative to no gate and to
  simpler baselines (B0–B3) — an existence-proof-scale empirical finding on this data, not a
  generalizable claim.
- Relative ranking of the four `EVALUATION_PLAN.md` conditions on this benchmark.
- Whether the gate's empirical risk-coverage curve dominates or is dominated by baseline
  gating strategies, on this data.
- Diagnostic/qualitative failure-mode findings (e.g. "the gate over-trusts patches that pass
  tests but touch import statements") — valuable even without statistical significance.

## 21. What conclusions this experiment could NOT support

- Any formal statistical coverage guarantee, unless exchangeability is confirmed AND
  literature review supports the method at this n — never assumed.
- Any generalization beyond §3's stated population.
- Any claim that Renacir "improves reliability" of CI/CD or software generally.
- Any novelty claim about the gating method — the contribution (if any) is honest applied
  evaluation, not new theory.
- Any claim that tier-2 (plausible) repairs are "as good as" tier-1 (correct) — the
  distinction is preserved in every downstream claim, no exceptions.
- Any claim about whether LLM self-reported confidence is calibrated *for code*, beyond what
  is directly measured on this benchmark — prior literature findings (even the already-vetted
  Kadavath et al. 2022) don't transfer without in-benchmark validation, especially given the
  already-vetted "Code Is More Than Text" / "Functional Entropy" papers suggesting code UQ
  differs from NLP UQ.
- Causal claims about *why* a gate over/under-abstains beyond what §9's ablations directly
  test.

---

## Unresolved methodological questions

Updated after the Phase 1.6 literature checkpoint (`docs/literature_review.md`). Four items
below were narrowed by that checkpoint (marked); the rest remain exactly as open as before —
narrowing an item's framing is not the same as resolving it, and none of the following is
decided by this freeze:

1. Exact target real:synthetic case ratio and total v1 case count (§11) — a resourcing
   decision, not a methods decision.
2. Minimum fraction of cases requiring an authored held-out test for tier-1 correctness
   (§7.1) — resourcing decision; affects how often tier-1 vs. tier-2 is even reachable.
3. Exact K, repeated runs per case (§14) — cost/power tradeoff, needs a budget number.
4. Repo-level splitting **scheme** (fixed split vs. LORO vs. grouped k-fold CV) and fold
   sizes (§13) — the repo-level grouping itself is a hard requirement; the scheme is not,
   pending final repo/case counts.
5. Minimum per-subgroup n before synthetic-vs-real breakdowns (§12) are more than
   descriptive.
6. **[Narrowed]** Calibration-summary methodology (§10.8) — naive histogram-binning ECE is
   now ruled out (literature-supported, see §10.8). Brier score vs. no scalar summary at all,
   and how to represent uncertainty around a calibration estimate, remain fully open.
7. Diagnosis-accuracy metric (§10.11) — line-level fault localization is a candidate only;
   final metric (including granularity/scoring) pending further APR/fault-localization
   literature review.
8. Real-case sourcing methodology itself (search strategy, license filtering, mining
   tooling) — not designed yet, a sub-methodology of its own.
9. **[Narrowed]** Contamination-risk handling for real cases (§19) — a concrete mitigation
   *policy* is now adopted (date-tracking, transparent flagging, no proof-of-absence claims,
   no exemption for popular curated datasets). Whether to exclude flagged cases entirely vs.
   report them with a caveat remains open, to be decided once real cases exist to flag.
10. Conservative vs. permissive aggregation rule for repeated runs (§14: "any failure counts
    as failure" vs. majority vote) — needs to be picked and frozen before data collection,
    not picked here.
11. **[Narrowed]** Conformal-style method choice (§9 B4) — the literature checkpoint found no
    candidate family (jackknife+, CV+, Mondrian, class-conditional, beyond-exchangeability)
    with established applicability to Renacir's repository-grouped structure (see §9's
    literature-checkpoint result). This is a documented negative finding, not merely "not yet
    selected" — but conformal prediction is not ruled out in general, only unsupported for
    Renacir so far. No method is selected.
12. Collector retrieval-completeness diagnostic (§5) — how to measure/report cases where
    Collector fails to surface a file needed for an in-scope gold patch — deferred until
    Collector is implemented.
13. **[New]** Repository-clustered uncertainty estimation generally (§16) — no method found
    (Clopper-Pearson, plain cluster bootstrap, or the MacKinnon & Webb wild-bootstrap lead)
    has been established as correctly accounting for repo-clustered proportions/paired-binary
    outcomes at Renacir's scale.
14. **[New]** AURC's precise finite-sample uncertainty at n≈30–50 (§10.4) — asymptotic
    consistency is established (Zhou et al. 2025); a usable finite-sample uncertainty figure
    at Renacir's exact scale is not.

## Literature questions — checkpoint status

Original questions from the freeze, with the Phase 1.6 checkpoint's answer where one exists.
Full detail, citations, and the full-read/metadata-only distinction are in
`docs/literature_review.md`; this is a status pointer, not a restatement.

1. Small-sample ECE estimation — **Answered**: not meaningfully estimable at n≈30–50 via
   naive histogram binning (Kumar/Liang/Ma 2019, Roelofs et al. 2022, both full-read).
   Whether an alternative is sufficient remains open (unresolved item 6).
2. Confidence intervals for risk-coverage curves at small n — **Not answered**. No source
   found giving a ready small-n method beyond the general Clopper-Pearson caveat in §16.
3. Repo-clustered/grouped conformal or cross-validation prior art — **Partially answered**:
   several candidate families exist (Mondrian, class-conditional/clustered conformal,
   beyond-exchangeability) but none has been shown to map onto Renacir's setting — see §9's
   literature-checkpoint result. A genuine negative finding, not an absence of search.
4. What SWT-Bench proposes operationally — **Answered** (full-read): differential fail→pass
   execution against the gold patch, not a held-out set; see §7.1(c).
5. Is contamination a documented, quantified concern for real historical-commit sourcing —
   **Answered**: yes, three converging sources (full-read), see §19's mitigation policy.
6. Whether code-specific UQ findings imply Kadavath et al.'s self-reported-confidence-
   calibration result shouldn't be assumed for code — **Not independently re-verified this
   checkpoint**; framing retained from the 2026-09-17 checkpoint, not newly confirmed.
7. Standard fault-localization accuracy metrics in APR literature — **Answered** (search-
   confirmed, not full-read): Top-N/line-level accuracy is standard practice; exact
   granularity for §10.11 remains open (unresolved item 7).
8. Re-confirm citation details for numbers before use — **Ongoing discipline, not a one-time
   answer**; no unconfirmed number (e.g. RisCoSet's improvement %) is used anywhere in this
   protocol or in `docs/literature_review.md`.
