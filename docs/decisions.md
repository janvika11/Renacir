# Decisions log

Dated record of scoping and framing decisions for Renacir. This is a planning document — no implementation exists yet.

## 2026-09-17 — Initial scope and hard safety constraints

- Renacir targets **Python + PyTest + GitHub Actions only** for the MVP. No other languages/CI systems until this scope is validated.
- The system **never auto-merges**. It may only open a PR or post an escalation report; a human always merges.
- Generated/untrusted code is **never executed outside an isolated Docker sandbox** (no network access, resource/time limits, ephemeral, non-root).

## 2026-09-17 — Reframe: the research contribution is the confidence gate, not the repair agent

The original framing ("a multi-agent system that repairs CI failures") sits in an already crowded space (SWE-bench agents, AutoCodeRover, Agentless, SWE-agent, OpenHands, etc.). The differentiator worth building the project around is **confidence-aware selective prediction / calibration for autonomous code repair** — deciding when a generated patch is trustworthy enough to propose vs. when to abstain and escalate to a human.

**Consequence:** the multi-agent repair pipeline (Collector → Diagnoser → Patcher → Validator) is now explicitly the *testbed* needed to generate (patch, correctness) pairs to study the gating problem — not the end goal. The Gatekeeper and its evaluation are the centerpiece.

### Literature checkpoint (added before Phase 4 — Gatekeeper design)

**Repair/agent side** — read to correctly position Renacir relative to existing work, not re-derive it:

| Paper | Venue / arXiv | Contribution |
|---|---|---|
| SWE-bench: Can Language Models Resolve Real-World GitHub Issues? (Jimenez et al.) | ICLR 2024 · [2310.06770](https://arxiv.org/abs/2310.06770) | Defines the standard benchmark (2,294 real GitHub issues, 12 Python repos) and eval protocol most repair-agent work is measured against. |
| SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering (Yang et al.) | NeurIPS 2024 · [2405.15793](https://arxiv.org/abs/2405.15793) | Shows the interface an LLM uses to view/edit code affects performance as much as the base model — relevant to how our Collector/Patcher expose repo context. |
| AutoCodeRover: Autonomous Program Improvement (Zhang et al.) | ISSTA 2024 · [2404.05427](https://arxiv.org/abs/2404.05427) | Combines an LLM with AST-based code search for autonomous fault localization + patch generation — a direct architectural comparison point for our Diagnoser+Patcher split. |
| Agentless: Demystifying LLM-based Software Engineering Agents (Xia et al.) | FSE 2025 · [2407.01489](https://arxiv.org/abs/2407.01489) | Shows a simple 3-stage localize→repair→validate pipeline (no autonomous agent loop) matches/beats complex agent scaffolding at much lower cost — supports keeping Renacir's pipeline simple. |
| OpenHands: An Open Platform for AI Software Developers as Generalist Agents (Wang et al.) | ICLR 2025 · [2407.16741](https://arxiv.org/abs/2407.16741) | General-purpose open coding-agent platform; useful contrast for positioning Renacir as narrow and safety/calibration-focused rather than general-purpose. |
| SWT-Bench: Testing and Validating Real-World Bug-Fixes with Code Agents | [2406.12952](https://arxiv.org/abs/2406.12952) | Benchmark centered on *validating* fixes rather than just generating them — directly informs what our Validator should check. |
| Automatic Programming: Large Language Models and Beyond (survey) | [2405.02213](https://arxiv.org/abs/2405.02213) | Broader taxonomy of LLM-based program repair approaches — useful for the SOP/related-work framing. |

**Gating side** — this is the actual novel angle; read closely:

| Paper | Venue / arXiv | Contribution |
|---|---|---|
| Selective Classification for Deep Neural Networks (Geifman & El-Yaniv) | NeurIPS 2017 · [1705.08500](https://arxiv.org/abs/1705.08500) | Foundational risk-coverage framework: reject low-confidence predictions to guarantee a target error rate. Conceptual basis for the Gatekeeper. |
| A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification (Angelopoulos & Bates) | 2021 · [2107.07511](https://arxiv.org/abs/2107.07511) | Accessible tutorial establishing distribution-free, model-agnostic coverage guarantees — the methodological reference if we go conformal. |
| Language Models (Mostly) Know What They Know (Kadavath et al.) | 2022 · [2207.05221](https://arxiv.org/abs/2207.05221) | Shows LLM self-reported correctness probabilities can be reasonably calibrated when elicited well — relevant to using the Diagnoser/Patcher's own stated confidence as a gate input. |
| Semantic Uncertainty: Linguistic Invariances for Uncertainty Estimation in NLG (Kuhn, Gal & Farquhar) | ICLR 2023 · [2302.09664](https://arxiv.org/abs/2302.09664) | Semantic entropy as an unsupervised uncertainty signal for open-ended generation, more predictive of correctness than naive baselines — transferable to scoring diagnosis/patch confidence. |
| Conformal Language Modeling (Quach et al.) | 2024 · [2306.10193](https://arxiv.org/abs/2306.10193) | Extends conformal prediction to generative LM outputs with formal coverage guarantees, via a calibrated stopping rule over sampled generations. |
| Calibrated Selective Classification | TMLR · [2208.12084](https://arxiv.org/abs/2208.12084) | Reframes selective prediction around whether the *confidence estimate itself* is trustworthy, not just its magnitude — sharper lens than a flat threshold. |
| ConU: Conformal Uncertainty in LLMs with Correctness Coverage Guarantees | EMNLP Findings 2024 | Applies conformal prediction to black-box LLM correctness via self-consistency, giving formal correctness-coverage guarantees — closest existing analogue to what we want the gate to guarantee. |
| Uncertainty Quantification for LLM-based Code Generation (RisCoSet) | 2026 · [2605.12201](https://arxiv.org/abs/2605.12201) | Reframes code UQ as multi-label (via Learn-Then-Test) instead of single-label/monotonic-risk PAC prediction sets; outputs a partial-AST prediction set guaranteed to contain a correct solution with high confidence. Most directly on-topic paper; read first. **Author list and the specific reported improvement % over the PAC-prediction-sets baseline are not yet independently confirmed here — verify against the PDF before citing either.** |
| Functional Entropy: Predicting Functional Correctness in LLM-Generated Code with UQ | 2026 · [2605.28500](https://arxiv.org/abs/2605.28500) | Introduces functional-equivalence-based UQ methods (incl. "functional entropy," a code-specific analog of semantic entropy); evaluated across 3 languages, 5 LLMs, 1,700+ problems — shows NLI-based semantic-equivalence methods fail on code because NLI can't tell functionally-different programs apart. |
| Code Is More Than Text: Uncertainty Estimation for Code Generation | 2026 · [2606.09577](https://arxiv.org/abs/2606.09577) | Argues code needs 3 orthogonal uncertainty axes beyond NL-style methods — lexical (token entropy), algorithmic (pseudo-code consistency), functional (behavioral consistency); their ensemble raises AUROC from 0.696 (best NL-derived baseline) to 0.776 across 5 code LLMs. Concrete, citable justification for why NLP-style calibration can't be borrowed wholesale for Renacir's Diagnoser/Patcher confidence signals. |
| Conformal Language Modeling (Quach, Fisch, Schuster, Yala, Sohn, Jaakkola, Barzilay) | 2023–24 · [2306.10193](https://arxiv.org/abs/2306.10193) | Calibrates a stopping rule that grows a sampled candidate set until it's confident the set contains an acceptable answer, plus a separate rejection rule to prune noise from that set — with a coverage guarantee. The direct bridge from Angelopoulos & Bates' base theory to *generative, multi-step* LM outputs, which is structurally close to Renacir's two-stage diagnosis→patch generation. |

Exact citation details (page numbers, final venue, and any specific reported metrics) should be re-verified against the published PDF before use in any written report — the above were checked against arXiv abstracts/listings but not read in full, and RisCoSet's author list and quoted improvement percentage specifically remain unconfirmed as of this entry.

## 2026-09-17 — Narrow v1 failure classes

v1 handles **assertion failures and import/dependency errors only**. Logic bugs and off-by-one errors are deferred to a later extension if time allows.

**Why:** broader failure classes are a scope risk against a semester timeline, and a narrower, well-understood failure surface makes it easier to build a small, honest, correctly-labeled dataset — which is the actual bottleneck resource for this project.

## 2026-09-17 — Dataset curation moved earlier (alongside Phase 1)

Originally planned for Phase 5 (after the full pipeline was built). Moved to run alongside Phase 1 so feasibility of a ~30–50 case, carefully curated, honestly-labeled benchmark is established before investing in the rest of the pipeline.

## 2026-09-17 — Gatekeeper design: single-stage calibrated gate (Option B), not two-stage

**Options considered:**

- **Option A — two-stage calibrated gate** (inspired by Quach et al.'s stopping/rejection structure): calibrate a separate acceptance rule after the Diagnoser and another after the Patcher, instead of one flat confidence number at the end. More faithful to the literature's exact mechanism, and structurally closer to how the pipeline actually works (two generative steps, either can introduce error). Rejected for v1 — see reasoning below.
- **Option B — single calibrated threshold, post-Validator** (chosen): one conformal-calibrated acceptance rule applied to the combined evidence (diagnosis confidence, patch characteristics, validator pass/fail) after the full pipeline has run. Two-stage gating is retained as explicit future work.

**Reasoning (why B, given a semester timeline and a ~30–50 case benchmark):**

- Split-conformal calibration's guarantee resolution is roughly `1/n`. With ~25–30 cases available for calibration (after reserving some for test), achievable coverage levels are already quantized in ~3–4% steps — coarse but reportable.
- Option A splits that already-small budget across *two* calibration events, leaving each stage ~15–20 cases. At that size the conformal quantile is essentially "the 1st or 2nd worst score in the set" — highly sensitive to which cases land in the split. A different random split would visibly change the reported guarantee. This is the concrete mechanism behind reviewer-visible p-hacking-adjacent handwaving, not just a vague risk.
- The two stages' guarantees also compound: valid end-to-end coverage requires either an alpha-budget split across stages (Bonferroni-style, which needs *more* data for any statistical power — the opposite of what we have) or a joint calibration procedure, which is more statistical machinery than a 30–50 case benchmark can support honestly.
- Faithfulness to Quach et al.'s exact structure is not itself a scientific goal. Their method was validated on datasets almost certainly one to two orders of magnitude larger than ours; porting the same machinery onto `n=30–50` without acknowledging that mismatch would cite the paper's mechanism while violating the assumptions that make its guarantee trustworthy.

**Refinement within Option B:** use a leave-one-out-style procedure (jackknife+/CV+) rather than plain split-conformal — at this sample size, holding out a separate calibration set wastes roughly half an already-small dataset. Report the coverage estimate with its own uncertainty (e.g., across repeated resampling), not a single point number.

**Revisit condition:** reconsider Option A (two-stage gating) if the benchmark grows past roughly 150–200 cases, or if a cheap way to generate additional synthetic calibration cases becomes available.

## 2026-09-17 — Gate must be built baseline-first; conformal methods are earned, not assumed

Correction to the previous entry's "use jackknife+/CV+" refinement: that got the sequencing backwards. Reaching for conformal machinery before checking whether it's needed — or whether its assumptions hold — risks the project reading as "added a fancy statistical method to sound advanced" rather than answering the actual question: *can Renacir estimate when a proposed repair is likely correct, and abstain when it isn't?*

**Required build order for the Gatekeeper:**

1. **Simple, transparent baselines first**, evaluated on ordinary held-out risk-coverage curves (no formal guarantee claimed):
   - A pure validation-based rule (propose iff the Validator passes with no new regressions).
   - A learned confidence model (e.g., logistic regression / gradient-boosted trees over diagnosis confidence, patch characteristics, validator outcome).
   - A classic threshold-based selective-prediction rule (Chow's rule / Geifman & El-Yaniv-style), calibrated via held-out risk-coverage analysis.
2. **Only after** these baselines are built and understood, investigate whether a conformal-style method (split-conformal, jackknife+/CV+) is *appropriate for this data* — not simply more sophisticated.

**Exchangeability must be checked, not assumed, before any coverage guarantee is stated.** Code-repair cases are not automatically exchangeable: cases drawn from the same repository plausibly share coding style, bug patterns, and dependency structure, so the benchmark may be clustered by repo rather than i.i.d. A conformal coverage guarantee is only valid under exchangeability between calibration and test points. Before claiming one:
   - Check whether the benchmark is repo-clustered, and if so, use a repo-stratified or leave-one-repo-out split rather than a random split.
   - If exchangeability can't be established, either scope the guarantee explicitly as conditional on this benchmark's specific repo mix, or don't state a formal guarantee at all — report the empirical risk-coverage curve instead and say so plainly.

**Reporting rule:** never state "the gate has X% guaranteed coverage" without (a) reporting the simpler baseline's empirical numbers alongside it for comparison, and (b) stating explicitly what exchangeability assumption the guarantee relies on and whether it was checked. If it wasn't, that's a stated limitation, not an asterisk to omit.

## 2026-09-17 — Evaluation must stress-test the gate specifically, not treat it as one metric among many

The confidence gate is now the primary object of study. The evaluation plan requires:
- Calibration curves / coverage-vs-risk tradeoffs for the gate.
- Comparison of **at least two distinct gating strategies** (e.g., a flat confidence threshold vs. a conformal/coverage-guaranteed approach), not just one threshold rule.
- An explicit plan to report honestly if the gate does **not** calibrate well — a negative or mixed result here is a legitimate, reportable finding, not something to hide or paper over.

## 2026-09-18 — Phase 1 benchmark/fixture infrastructure complete (preliminary)

Built `benchmarks/` (manifest, per-case fixtures, ground-truth unified-diff patches) and
`src/renacir/benchmark/` (pydantic manifest schema, discovery, isolated-subprocess runner,
CLI), per the approved Phase 1 proposal. Collector and Diagnoser — the rest of Phase 1 —
are not started; this entry covers the fixture/benchmark half only.

**Status is explicitly preliminary:** the benchmark contains **2 synthetic cases** (one
assertion failure, one import failure) — proof that the manifest/discovery/runner/CLI
machinery works end-to-end, not a claim about benchmark coverage. `EVALUATION_PLAN.md`'s
~30–50 case target is unmet and unaffected by this entry; growing the case count is separate,
ongoing work.

**Verified before marking complete:**
- Both cases deterministically fail pre-patch and pass post-patch (`renacir-benchmark run`,
  repeated 3x, plus manual `pytest -q` inside each fixture directory) — checksums of the
  fixture source files confirmed the isolated-subprocess runner never mutates the originals.
- The manifest schema (`renacir.benchmark.models`) rejects malformed input (missing required
  field, invalid category literal), not just accepts valid data.
- `renacir.benchmark.discovery.validate_case_paths` rejects a case pointing at a nonexistent
  directory.
- The CLI's `list`, `run` (all cases), `run <id>`, and unknown-id error path all behave
  correctly.
- Full `pytest`, `ruff check .`, and `ruff format --check .` all pass.

**Discrepancy found and fixed, not silently:** the initial implementation's isolation of
`benchmarks/` from Renacir's own test collection relied only on `testpaths = ["tests"]` in
`pyproject.toml`. `testpaths` is a *default*, not an *exclusion* — it's dropped the moment any
path is passed explicitly. `pytest .` (a plausible IDE or CI-wrapper invocation) collected the
import fixture's intentionally-broken code and crashed the whole run with an `ImportError`
during collection, rather than a clean, scoped test failure. Fixed by adding
`addopts = "--ignore=benchmarks"` to `[tool.pytest.ini_options]`. Verified after the fix:
bare `pytest` (9 passed) and `pytest .` (9 collected, no crash) are both safe; deliberately
targeting a fixture directly (`pytest benchmarks`, or `cd`-ing into a fixture and running
`pytest -q` as the README's manual-reproduction workflow instructs) still surfaces the
fixture's real failure, as intended — the fix only closes the *accidental* collection path.

## 2026-09-18 — Phase 1.5 research protocol frozen

`docs/research_protocol.md` is frozen, defining the primary/secondary research questions,
target population and scope, benchmark inclusion/exclusion criteria, the tier-1/tier-2/
incorrect correctness taxonomy, the abstention/escalation definition, primary metrics
(coverage, selective risk, the risk-coverage curve) and secondary metrics, Gatekeeper
baselines and ablations, dataset construction methodology, synthetic-vs-real reporting
policy, repository-level dev/calibration/test separation, repeated-run policy, logging
requirements, the statistical analysis plan, threats to validity, data-leakage prevention,
and explicit scope on what conclusions the eventual experiment can and cannot support — all
before any of Collector, Diagnoser, Patcher, Validator, Gatekeeper, or Orchestrator is
implemented.

Two methodological corrections were made during review, before freezing:
- Benchmark inclusion/exclusion criteria were decoupled from Collector's future retrieval
  behavior. A case's validity is determined by the declared task population and scope
  (`PROJECT_SPEC.md`), not by what a not-yet-built component would retrieve. A Collector
  that fails to surface a needed file is a pipeline/retrieval failure to measure later, not
  grounds to exclude the case now.
- The tier-1/tier-2/incorrect correctness taxonomy was clarified to state explicitly that
  correctness never requires syntactic/structural similarity to the gold patch — only
  behavioral agreement (tests pass, no regression, plus one independent check). Multiple
  semantically valid repairs may exist for a case.

**Explicitly left unresolved by this freeze** (full list in `docs/research_protocol.md`'s
"Unresolved methodological questions" section): calibration-summary methodology (ECE vs.
Brier vs. alternatives), the repository-level split scheme (fixed split vs. leave-one-repo-
out vs. grouped k-fold — repo-level grouping itself is frozen as a hard requirement, the
scheme is not), the final diagnosis-accuracy metric, any conformal/split-conformal/
jackknife+/CV+ method choice, the number of repeated runs (K) per case and its aggregation
rule, and the real:synthetic benchmark case ratio. These require either the literature
review or benchmark-scale data not yet available, and are deliberately not pre-decided here.

Minimal consistency updates were made to `PROJECT_SPEC.md`, `ARCHITECTURE.md`, and
`EVALUATION_PLAN.md` alongside this freeze (pointers to the protocol as the authoritative
source for metric definitions, and softening `ARCHITECTURE.md`'s Gatekeeper-input wording so
it no longer presupposes Diagnoser confidence is a settled gate input). No other files
changed; no agent code was implemented; no dependencies were added; the literature review has
not started.

## 2026-09-18 — Phase 1.6 literature checkpoint completed; four evidence-sufficient decisions adopted

`docs/literature_review.md` records a targeted literature checkpoint against the specific
unresolved questions in `docs/research_protocol.md` — not a general survey. Sources were
independently verified this pass (title/author/venue/identifier cross-checked against ≥2
sources each), and the highest-stakes claims were confirmed by reading the primary paper in
full rather than relying on an abstract; full-read vs. metadata-only status is recorded per
source in `docs/literature_review.md` §11.

**Four decisions were evidence-sufficient and are now reflected in `docs/research_protocol.md`:**

1. **Naive equal-width histogram-binning ECE is rejected** as the primary scalar calibration
   summary at Renacir's expected n≈30–50 (§10.8). Full-text evidence from Kumar, Liang & Ma
   (NeurIPS 2019) and Roelofs et al. (AISTATS 2022) independently show sample requirements
   one to three orders of magnitude above Renacir's scale. Brier score vs. no scalar summary,
   and how to represent calibration uncertainty, remain unresolved — this decision narrows
   the calibration question, it does not close it.
2. **The tier-1/tier-2/incorrect correctness taxonomy and the no-syntactic-similarity rule
   are literature-confirmed, not revised** (§7.1). Full-text evidence from Qi et al. (ISSTA
   2015), SWT-Bench (NeurIPS 2024), and PatchDiff (arXiv 2503.15223) converges on: test-suite
   passage is necessary but not sufficient for correctness, and behavioral divergence from a
   gold patch is not automatically evidence of incorrectness. Renacir's existing taxonomy is
   preserved as-is; PatchDiff's own taxonomy/thresholds are not adopted in its place.
3. **A concrete contamination-mitigation policy is adopted for real historical cases**
   (§19): record fix dates and model/training-cutoff information where available, flag (never
   silently exclude) cases whose timing makes contamination plausible, distinguish diagnostic
   evidence of memorization from direct proof (there is none, for any specific case), never
   claim a case is proven uncontaminated, and do not treat a popular curated real-bug
   database (e.g. BugsInPy) as exempt from the same risk class as SWE-bench merely because it
   differs in language scope or size. Full-text evidence from SWE-Bench Illusion, SWE-rebench,
   and SWE-bench's own (insufficient) internal check.
4. **Clopper-Pearson is retained for descriptive binomial intervals, with an explicit new
   scope limitation** (§16): it does not itself account for repository clustering. This
   limitation is now stated directly rather than left implicit.

**Conformal prediction was NOT selected, and repository-clustered uncertainty estimation
remains unresolved** (§9, §16). By direct reading, jackknife+/CV+ (Barber et al. 2021)
explicitly states its guarantees likely fail under correlated within-group observations; the
two "beyond exchangeability" papers found (Barber et al. 2023; Oliveira et al. 2024) both
target temporal drift, not discrete-group dependence, despite superficially relevant framing;
class-conditional/"clustered" conformal prediction (Ding et al. 2023) clusters prediction
classes with too few examples, a different problem from repository dependence that happens to
share a word; Mondrian conformal prediction (Vovk et al. 2003, unpublished) is the closest
structural match but its own known failure mode is too few examples per group — the likely
regime for most of Renacir's repositories. **This is recorded as a genuine negative finding,
not a search gap: no conformal method examined has established applicability to Renacir's
repository-grouped, small-n, stochastic-output structure.** Conformal prediction is not ruled
out in general — only unsupported for Renacir so far. Separately, MacKinnon & Webb's wild
cluster bootstrap (2018) is recorded only as a candidate lead for the unresolved
repository-clustered-uncertainty question (§16): its small-cluster-count result is from a
regression treatment-effect setting, not established as applicable to Renacir's
proportion/paired-binary setting, and it is not adopted.

**AURC remains secondary to the risk-coverage curve**, unchanged (§10.4). Zhou et al. (ICML
2025, metadata-verified only) establish asymptotic consistency for finite-sample AURC
estimators, but the finding does not supply a usable finite-sample uncertainty figure at
Renacir's scale — this is recorded as still unresolved, not as new justification either way.

**Left explicitly unresolved by this checkpoint** (full list and reasons in
`docs/research_protocol.md`'s "Unresolved methodological questions"): Brier vs. no scalar
calibration summary, calibration-uncertainty representation, the repo-level split scheme
(LORO vs. grouped k-fold vs. fixed), the exact diagnosis-accuracy metric/granularity, the
Collector retrieval-completeness diagnostic, which (if any) conformal method to use, K
repeated stochastic runs, the repeated-run aggregation policy, the real:synthetic benchmark
ratio, a clustered paired-comparison method, repository-clustered uncertainty estimation
generally, and AURC's precise finite-sample uncertainty at n≈30–50.

No Renacir component (Collector, Diagnoser, Patcher, Validator, Gatekeeper, Orchestrator) was
implemented. No benchmark code was modified. No dependencies were added. Only
`docs/literature_review.md` (new), `docs/research_protocol.md`, and this file were changed;
`PROJECT_SPEC.md`, `ARCHITECTURE.md`, and `EVALUATION_PLAN.md` were reviewed for factual
consistency and required no changes.
