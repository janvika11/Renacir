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

## 2026-09-18 — Phase 2 benchmark-curation methodology approved (with revisions); Phase 2A schema migration and curation infrastructure complete

The Phase 2 benchmark-curation methodology (expanding the 2-case synthetic benchmark toward
~30–50 cases, two source tracks — controlled synthetic and reproducible real-world) was
proposed, reviewed, and approved **with eight corrections** before any implementation:

1. Removed the hard ≤5,000-LOC/≤50-file repository-size inclusion gate — replaced with
   task-level tractability criteria (reproducible, bounded test scope, localized repair,
   fits the eventual sandbox budget). Repo size is now descriptive metadata only.
2. Replaced "gold patch"/"single agreed gold patch" with **reference repair** for the
   schema and curation vocabulary: a known-good state useful for provenance and
   correctness-check construction, explicitly not claimed to be the only valid repair.
3. Removed the blanket "multi-file refactor" rejection rule — replaced with a localization
   criterion (changed files within the failing test's dependency closure), with any
   file-count number labeled a pragmatic pilot heuristic, not a research claim.
4. Removed the implicit Python-3.11-for-every-case requirement — real cases record their own
   runtime/dependency/install requirements; Renacir's own 3.11+ requirement is separate.
5. Revised the leakage architecture so repository/library **identity** exposure to a future
   model-facing context is an explicit, unresolved experimental/design variable (not
   auto-hidden) — while provenance and reference-repair data remain strictly hidden always.
6. Relabeled the ≥5-rerun reproducibility rule explicitly as a versioned pilot heuristic, not
   a statistical non-flakiness guarantee.
7. Defined an explicit four-tier field classification (execution / potentially model-facing /
   evaluator-only / reference-repair-only) with enforcement by typed allowlist, not file
   location alone.
8. Replaced `repository_id = "synthetic:<case-id>"` (one singleton group per synthetic case)
   with `source_group_id`, shared across synthetic cases derived from the same template,
   unified with the same field's role for real cases.

**Phase 2A (this entry) implements the schema migration and curation infrastructure only —
no cases were curated, no dataset was downloaded, no repository was mined.**

- `expected_repair`/`ExpectedRepair`/each case's `expected/` directory renamed to
  `reference_repair`/`ReferenceRepair`/`reference/` throughout (manifest, Pydantic models,
  discovery, runner, tests, fixtures, README). No compatibility alias retained — only 2
  internal fixtures existed and there are no external schema consumers. Directory renames
  used `git mv` to preserve history.
- `benchmarks/manifest.json` bumped to `schema_version: 2` with `execution`, `source`, and
  `curation` metadata blocks per case, per the approved schema (full reference:
  `docs/benchmark_schema.md`). `discovery.load_manifest` now rejects an unsupported
  `schema_version` rather than silently accepting it.
- New `src/renacir/benchmark/context.py`: `ModelFacingContext`, an explicit Tier-B allowlist
  type with no field overlapping Tier C/D metadata, plus `build_model_facing_context()`
  reading only `failing_test`/`command`/`category` from a case. `repository_identity` exists
  as a field, defaulted to `None` — deliberately unresolved, per correction 5 above.
  Collector does not exist and is not implemented; this only fixes the shape a future one
  must build into.
- New `src/renacir/benchmark/curation.py`: `CandidateCurationRecord`/`CandidateCurationLog`
  for real-world candidate decisions (accepted and rejected), stored separately in the new
  `benchmarks/candidates.json` — currently empty (`records: []`), since no real-world
  candidate has been reviewed yet.
- Both existing synthetic fixtures migrated to the new schema and given **distinct**
  `source_group_id`s (`synthetic:assertion-off-by-one-denominator`,
  `synthetic:import-stale-name-after-rename`) — they are genuinely different bug mechanisms,
  not artificially split; future synthetic cases sharing a template are expected to share a
  `source_group_id`.
- New `docs/benchmark_schema.md`: the authoritative field reference and four-tier boundary
  documentation, including the case-specific-runtime implication for the future Validator
  (likely needs case-specific runtime images, not one fixed Renacir-wide image — recorded now
  as a forward design note, not solved).
- Minimal consistency fixes: `docs/research_protocol.md` §11 and `EVALUATION_PLAN.md`'s
  benchmark-strategy bullet updated from "schema extension is future work" (now stale) to
  reflect the implemented schema, using reference-repair language. `README.md`'s Benchmark
  section updated to match.

**Explicitly not claimed**: the benchmark is still 2 synthetic cases. Nothing about 30–50
cases, real-world sourcing, or a specific real:synthetic ratio is claimed to exist.

**Left unresolved, unaffected by this infrastructure work**: repository-level split scheme
(LORO/grouped k-fold/fixed), real:synthetic ratio, exact sandbox resource/time limits,
repository-identity exposure (now explicitly a design variable per correction 5, still
undecided), calibration-summary methodology beyond ruling out naive ECE, conformal method
choice, K repeated runs and aggregation policy — all exactly as open as recorded in
`docs/research_protocol.md`.

Verified before considering Phase 2A complete: full `pytest` suite passes (schema validation,
malformed-metadata rejection, reference-repair loading, Tier B/C/D structural separation,
rejected-candidate representability, both fixtures still fail-then-pass through the harness),
`ruff check .` and `ruff format --check .` clean, `git diff --check` clean, benchmark CLI
(`list`/`run`) exercised manually against the migrated schema. No Collector, Diagnoser,
Patcher, Validator, Gatekeeper, or Orchestrator code was added. No dependencies were added.

## 2026-09-18 — Phase 2B synthetic pilot expansion (2 → 9 cases)

Expanded the synthetic benchmark from the 2 Phase 1 infrastructure-validation cases to a
9-case synthetic pilot, using the Phase 2A schema. **This is a pilot, not the final research
benchmark** — no real-world curation has started, and no claim of statistical
representativeness is made. `EVALUATION_PLAN.md`'s ~30–50 case target remains unmet.

**Final deduplication check, before implementation** (required by the approved Phase 2B
plan): the two candidates flagged as closest to the existing fixture were each compared on
root cause, failure shape, diagnostic information needed, repair operation, and
correctness-check design.
- `assertion-tax-wrong-constant` vs. `assertion-average-off-by-one`: matched on every
  dimension (both: wrong numeric literal in a single-expression computation, wrong-magnitude
  scalar failure, one-line-formula diagnosis, single-token repair, differential-sweep check).
  **Dropped** — not built, no replacement manufactured. Recorded as a rejected candidate in
  `benchmarks/candidates.json` with the comparison as its rejection reason.
- `assertion-truncate-empty-edge-case` vs. `assertion-average-off-by-one`: differed on every
  dimension (comparison-operator boundary bug vs. arithmetic-operand bug; control-flow/string
  failure vs. numeric-magnitude failure; boundary-inclusivity reasoning vs. formula-checking;
  operator swap vs. operand removal; boundary-sweep check vs. numeric-differential check).
  **Kept.**

**9 accepted cases, 5 assertion / 4 import, across 6 source groups**:

| Source group | Cases |
|---|---|
| `synthetic:assertion-off-by-one-denominator` | `assertion-average-off-by-one` (Phase 1) |
| `synthetic:import-stale-name-after-rename` | `import-renamed-helper` (Phase 1) |
| `synthetic:billing-template` | `assertion-discount-boolean-logic` |
| `synthetic:textstats-template` | `assertion-tags-mutable-default`, `assertion-truncate-empty-edge-case` |
| `synthetic:config-fallback-standalone` | `assertion-config-fallback-default` |
| `synthetic:reportpkg-template` | `import-reportpkg-missing-reexport`, `import-reportpkg-bad-local-import`, `import-reportpkg-broken-init` |

`billing-template` intentionally hosts only 1 case (its sibling candidate was dropped above)
rather than being backfilled to look less like a singleton — grouping reflects genuine
template-sharing, not a target group size.

**7 of 9 cases carry an independent, evaluator-only correctness check**
(`reference/independent_check.py`) beyond the originally-failing test — boundary sweeps,
cross-call state checks, or import-signature/delegation checks. The 2 Phase 1 cases don't
have one yet (a recorded gap, not new work in scope here). Every check was verified to pass
against the reference-repaired code independently of the harness, before being wired in.

**Leakage architecture change, discovered during implementation, not improvised around**:
building the independent-check mechanism required actually staging additional files for
evaluator-only execution, which surfaced that `renacir.benchmark.runner.staged_case`
previously copied a case's entire directory — including `reference/` — into the isolated test
directory every run. This never affected pass/fail correctness (nothing under `reference/`
matched pytest's discovery pattern), but it left Tier D material physically present in the
same tree a future Collector would scan, independent of `ModelFacingContext`'s own field
allowlist. Fixed: `staged_case` now excludes `reference/` entirely; the reference-repair patch
is read from the original case directory when applied; independent-check files are copied in
individually, only after the repair is already applied. Verified by a new test
(`test_staged_case_never_contains_reference_directory`) and by the full existing suite still
passing unchanged for the 2 Phase 1 cases.

**Second infrastructure issue discovered and fixed, not routed around**: `import-reportpkg-
broken-init`'s intentional bug (a stale import of a removed symbol) also trips Renacir's own
`ruff` `F401` (unused-import) rule — the first fixture whose bug happens to overlap with a
selected lint rule. Fixed by excluding `benchmarks/` from `ruff` entirely
(`extend-exclude = ["benchmarks"]` in `pyproject.toml`), on the principle that intentionally-
broken fixture code should never be held to Renacir's own lint standard — not by reshaping the
bug to dodge the linter.

**Reproducibility**: each of the 7 new cases was run 5 consecutive times through the full
harness (`renacir-benchmark run <id>`) with identical results every time — deterministic
pre-repair failure, post-repair success, independent check pass. Per
`docs/benchmark_schema.md`, this is the pragmatic Phase 2 pilot heuristic
(`reproducibility_check_version: "pilot-5x-v1"`), not a statistical non-flakiness guarantee.
Fixture file checksums were confirmed unchanged after every run (staging copies, never
mutates, the source fixtures).

**Verified before considering Phase 2B complete**: full `pytest` suite and unrestricted
`pytest .` both pass with all 9 cases collected only through the harness, never through
Renacir's own test collection; `ruff check .` and `ruff format --check .` clean; every case
individually exercised through `renacir-benchmark run <id>`; `git diff --check` clean.

**Left unresolved, unaffected by this pilot expansion**: repository-level split scheme,
real:synthetic ratio, exact sandbox resource/time limits, repository-identity exposure,
calibration-summary methodology beyond ruling out naive ECE, conformal method choice, K
repeated runs and aggregation policy — all exactly as open as recorded in
`docs/research_protocol.md`. No Collector, Diagnoser, Patcher, Validator, Gatekeeper, or
Orchestrator code was added. No LLM or GitHub API integration was added. No new dependency
was added (the `ruff` config change is not a dependency). No real-world dataset was
downloaded and no real-world case was curated.

## 2026-09-18 — Phase 2C/2D real-world discovery and reproduction; Phase 2E implementation (9 → 12 cases)

**Phase 2C/2D (discovery and reproduction, prior to this entry's implementation work)**
screened real-world candidates across BugsInPy, SWE-bench (structurally), and direct
repository mining (tqdm, httpie, sanic, cookiecutter, thefuck, PySnooper, click, attrs),
introducing a taxonomy to keep two distinct evidentiary standards from being conflated:

- **REAL-CI-A/B/C**: a candidate qualifies only if primary-source evidence shows the failure
  predates its repair — (A) a pre-existing failing automated test, (B) a preserved CI run/log,
  or (C) a pre-fix bug report containing a reproducible failing test/command. **C explicitly
  does not require the pytest regression artifact itself to predate the fix** — most mature
  projects add that alongside the fix (a "retrospective regression test"); conflating the two
  was identified and explicitly guarded against throughout.
- **HOLD — REAL-HISTORY/RETROSPECTIVE-TEST**: a real, reproducible historical bug that does not
  meet the REAL-CI-A/B/C bar. Not "rejected" (invalid) — a distinct, structurally-preserved
  outcome. `tqdm-tenumerate-start` (buggy/fix commits ~2 hours apart on the same feature
  branch, never shipped to a release) and `thefuck-pip-unknown-command` (a real production
  stack trace exists, but the catching pytest artifact was added with the fix) were both fully
  reproduced and are held, per this entry's explicit instruction, not implemented.

A "zero test files touched in the fix commit" screening heuristic, applied at scale across
20+ commits in 5+ repositories (thefuck alone: 17/17 retrospective), found exactly one
REAL-CI-A candidate (`attrs`, commit `b950cb8d83`) — rejected separately, for reproducibility:
the bug only manifests under Nuitka-compiled Python, not standard CPython. **0 REAL-CI-A/B
candidates were ultimately usable; exactly 3 REAL-CI-C candidates were found and fully
reproduced** — `httpie-none-header-skip` (#412), `httpie-custom-host-header` (#235),
`click-path-resolve-symlink` (#1921) — meeting the approved target of 3.

**Phase 2E implements exactly these 3 as executable `BenchmarkCase`s** (9 synthetic → 9 + 3 =
12 total), per the approved plan's explicit constraint: `tqdm-tenumerate-start` and
`thefuck-pip-unknown-command` remain HOLD-only, never silently reclassified.

**Architecture: reconstruction recipes, not vendoring.** No upstream production source is
stored in this repository. `BenchmarkCase.upstream` (new, `None` for every synthetic case)
records pinned commits, license, REAL-CI subtype, two distinct runtimes (`historical_runtime`
vs. `reconstruction_runtime`, never conflated), and an explicit `preparation_steps` recipe
(clone → checkout → venv → install) that `renacir.benchmark.reconstruction.prepare_case`
executes into a local, git-ignored, disposable cache (`.benchmark-cache/`) — never applying
the reference repair during preparation. This enforces a **preparation vs. evaluation** split:
`prepare_case` is the only network-requiring function for a real case (idempotent, cached);
`evaluate_case` raises `PreparationRequiredError` rather than reaching the network if a real
case hasn't been prepared yet. The prepared checkout has its `.git` directory deleted
immediately after checkout — no reachable future/fix-commit history sits in the local cache at
all, closing a leakage vector unique to git-clone-based reconstruction that vendored fixtures
never had. No Docker-per-case infrastructure was needed or added (plain `venv` + `subprocess` +
`git` sufficed for all 3 verified recipes); no new dependency was added to Renacir's own
`pyproject.toml` (the historical dependencies installed by `prepare_case` are the *case's* own,
into a disposable venv, never Renacir's).

**A new leakage boundary, specific to real cases**: where a case's failing test is itself a
retrospective regression test (true for all 3), it's stored as `reference/repro_test.py` and
referenced by a new `test_overlay` field (`RetrospectiveTestOverlay`) — Tier D, like
`reference/fix.patch`, but needed for *both* pre- and post-repair evaluator runs, unlike
independent checks. Initial implementation copied it directly into `staged_case()`'s general
copy — which would have left it visible to a hypothetical future Collector calling
`staged_case()` on its own, the same class of leak Phase 2B fixed for `reference/` itself.
**Fixed before being left in, not after**: `staged_case()` never touches `test_overlay`;
`evaluate_case` applies it on its own private staged instance via a new
`apply_test_overlay`, mirroring how `apply_reference_repair` already works outside, not inside,
`staged_case`. Verified by
`tests/benchmark/test_context.py::test_staged_case_never_contains_test_overlay_target`.

**Three real bugs hit and fixed during implementation, not routed around**:
1. `pip install -e` for a real case's package makes Python imports resolve back to the
   persistent `.benchmark-cache/` checkout regardless of what gets copied into a given
   evaluation's staged (pre- or post-repair) directory — silently defeating reference-repair
   application (click's case: post-repair run kept failing identically to pre-repair). Fixed by
   never using an editable install for real cases; `runner._subprocess_env` instead prepends
   `PYTHONPATH` with the *staged* checkout's own `upstream.package_root` (new field, `"."` for
   httpie's flat layout, `"src"` for click's).
2. `setuptools` ≥ 81 (2025) removed `pkg_resources` entirely, breaking both `httpie` cases
   (2016/2014-era code importing it directly). Fixed by pinning `setuptools<81` in
   `preparation_steps`.
3. `requests==2.9.1` (an attempted historically-closer pin for `httpie-custom-host-header`)
   imports the stdlib `cgi` module, removed in Python 3.13+. Fixed by using unpinned modern
   `requests` instead, relying on the already-present, `hasattr`-guarded
   `requests.compat.is_windows`/`is_py3`/`is_py26` compatibility shim rather than an exact
   historical pin.

**Source grouping**: the two `httpie-*` cases share `source_group_id: "real:httpie-cli"` (same
upstream repository); `click-path-resolve-symlink` has its own, `"real:pallets-click"`.

**Licensing**: all 3 cases' stored `reference/` artifacts (a several-line diff, a small
Renacir-authored-or-adapted test) are from BSD-3-Clause-licensed repositories
(`httpie/cli`, `pallets/click`), verified against each repository's `LICENSE`/`LICENSE.rst`
file at the pinned commit — reviewed explicitly before storing anything, per the approved
plan's requirement. Only these small, attributed, evaluator-authored-or-derived artifacts are
stored; the buggy production source itself is never vendored, always freshly cloned by
`prepare_case`.

**`benchmarks/candidates.json`**: extended with a third `decision` value, `"held"` (distinct
from `"rejected"`, carrying a new `hold_reason` field), used for both HOLD candidates above;
plus 3 new `"accepted"` records for the implemented cases, each with `benchmark_case_id`
pointing at its manifest entry.

**Reproducibility**: each of the 3 real cases verified through the full `prepare` →
`evaluate_case` cycle 5 consecutive times — deterministic pre-repair failure, deterministic
post-repair success, deterministic independent-check pass (same `"pilot-5x-v1"` heuristic as
synthetic cases). For `click-path-resolve-symlink`, additionally confirmed the independent
check's two unaffected sub-cases (absolute-target symlink; plain non-symlinked path) pass on
the *buggy* checkout too — demonstrating they are genuine regression guards, not accidentally
bug-sensitive; this was an explicit requirement of the approved plan.

**Verified before considering Phase 2E complete**: full `pytest` suite (156 tests, including
new coverage for real-world provenance schema, optional-for-synthetic behavior, REAL-CI
subtype validation, the two-runtime distinction, compatibility-adaptation metadata,
source-group behavior, reconstruction-step validation, the `test_overlay` leakage boundary,
reference-repair/independent-check isolation, and unrestricted `pytest`'s continued inability
to collect `benchmarks/` or `.benchmark-cache/`) and unrestricted `pytest .` both pass;
`ruff check .` and `ruff format --check .` clean; `git diff --check` clean; all 12 cases
individually exercised through `renacir-benchmark run <id>`, all passing (pre-patch fail,
post-patch pass, independent checks pass); no reference repair, independent check, or
retrospective test ever staged into the model-visible tree; no solution-revealing issue/PR
discussion stored or exposed; synthetic cases' behavior unchanged (verified by the full
existing suite still passing).

**Explicitly not claimed**: that 3:9 is a final or representative real:synthetic ratio; that
REAL-CI-A/B candidates don't exist anywhere (only that none were found in this search); that
the historical runtime is pinned to the precision the reconstruction runtime is (recorded
separately, on purpose). **Left unresolved, unaffected by this work**: everything listed as
unresolved in `docs/research_protocol.md` and `docs/benchmark_schema.md` — repository-level
split scheme, real:synthetic ratio, exact sandbox resource/time limits, repository-identity
exposure, calibration-summary methodology, conformal method choice, K repeated runs and
aggregation policy. No Collector, Diagnoser, Patcher, Validator, Gatekeeper, or Orchestrator
code was added. No LLM or GitHub API integration was added. No new dependency was added to
`pyproject.toml`. No Docker-per-case infrastructure was added.

## 2026-09-19 — Phase 3: Collector implemented

The first real pipeline component, `src/renacir/collector/` (`models.py`, `parsing.py`,
`context_selection.py`, `collector.py`), plus a new top-level CLI (`src/renacir/__main__.py`,
`python -m renacir collect <case-id>`). Benchmark dataset unchanged (still 9 synthetic + 3
real, per Phase 2E) — this phase is pipeline implementation, not benchmark work.

**Design approved before implementation**, including one explicit information-boundary
decision for retrospective test overlays (real cases whose failing test was introduced by the
historical fix, per Phase 2E): the overlay may be applied and executed to reconstruct the
historical failure, and Collector may observe/report the resulting stdout, stderr, exit code,
parsed exception type/message, and traceback file:line locations — but its source text must
never appear in `CollectorOutput`, and `context_selection.select_context` must never include
it even when a traceback frame points directly at it. A new `failing_test_provenance` field
(`"original_fixture"` | `"reconstructed_retrospective_overlay"`) lets a future Diagnoser know
reconstruction occurred without ever receiving the withheld content. For an ordinary synthetic
case, the failing test's source remains legitimately Tier B, included under the normal bounded
context-selection rules — this asymmetry is deliberate and documented in `docs/collector.md`,
not silently uniform.

**Reuses, doesn't duplicate**: `CollectorOutput.context` embeds
`renacir.benchmark.context.ModelFacingContext` directly. Staging/execution reuses
`renacir.benchmark.runner.staged_case`/`apply_test_overlay`/`run_tests` as-is; `run_tests`
gained one small, additive, backward-compatible parameter (`extra_args: list[str] | None =
None`, default identical to prior behavior) so Collector can request pytest's `--tb=line`
format for reconstructed cases without touching `case.command` or `evaluate_case`'s own
behavior. Collector never calls `apply_reference_repair` or `run_independent_checks` — it only
ever observes the failing state.

**Three discrepancies found and fixed during implementation, not routed around** (full detail
in `docs/collector.md`'s "Determinism and path redaction" section):
1. Stale `.pyc` bytecode copied from the original fixture directory (left over from earlier
   direct `pytest -q` runs) could be reused instead of recompiled, causing pytest's traceback
   trailer to print the *original fixture's* absolute host path instead of one relative to the
   current staged copy — silently defeating the path-normalization filter meant to exclude
   dependency/venv frames, and emptying out context selection entirely for one synthetic case
   during testing. Fixed by purging `__pycache__`/`.pytest_cache` from Collector's own staged
   copy before running — scoped to Collector only.
2. An initial redaction pass (replacing the staged tempdir's absolute path with a
   `<case-root>` placeholder) ran *before* parsing, which corrupted every traceback frame path
   into an unresolvable literal and silently emptied `selected_context` for real cases. Fixed
   by parsing against the original, unredacted text (frame-path normalization uses
   `Path.relative_to`, not string matching) and redacting only afterward, for storage/display.
3. `click-path-resolve-symlink`'s test uses pytest's own `tmp_path` fixture, whose absolute
   path embeds the local OS username and a non-deterministic per-run counter
   (`/private/var/.../pytest-of-<user>/pytest-<N>/...`) — neither the staged root nor the
   reconstruction cache, so the fix above didn't catch it, and it broke both the
   host-path-leakage guarantee and the "deterministic repeated collection" test. Fixed with a
   residual regex redaction of any path remaining under `tempfile.gettempdir()`.

**A known, stated v1 limitation, left as such rather than silently expanded**:
context-selection rule 3 (local imports of the failing test file) is single-hop, not
transitive. For `import-renamed-helper`, `helpers.py` — arguably the most relevant file, since
it contains the renamed/missing symbol — is one import hop beyond what rule 3 reaches and
produces no traceback frame either (Python's `ImportError` doesn't emit a location trailer for
the module that failed to provide the name). Documented in `docs/collector.md` rather than
fixed, since making rule 3 transitive wasn't part of the approved design and would weaken the
bounded/narrow/explainable property Phase 3 was scoped around.

**Documentation consistency corrections made, scoped narrowly as requested** (not a general
cleanup pass): `docs/research_protocol.md` §5's repository-size criterion now states it's
descriptive metadata (`source.repository_size`), not an active ≤5,000-LOC/≤50-file hard gate,
matching the Phase 2 revision already recorded above; §18/§19's stale `expected/` terminology
(pre-dating the Phase 2A `reference/` rename) replaced; the integrity-checklist table's broken
`§20` cross-reference (pointing at "what conclusions this experiment could support," not a
leakage section) corrected to `§19`, the section actually titled "Data leakage risks and
prevention." Other previously-identified staleness (e.g. "gold patch" phrasing elsewhere in
§5) was left untouched, out of scope for this narrow correction pass.

**Verified before considering Phase 3 complete**: full `pytest` suite (233 passed — 156
pre-existing + 77 new Collector tests: schema, real execution capture, assertion- and
import-failure parsing, deterministic context selection, limit enforcement, fixture
immutability, malformed/no-traceback handling, deterministic repeated collection, and the full
forbidden-field/string/reference-repair/independent-check/retrospective-overlay leakage sweep,
run against multiple synthetic cases and all 3 reconstructed real cases) and unrestricted
`pytest .` both pass; `ruff check .` and `ruff format --check .` clean; `git diff --check`
clean; `python -m renacir.benchmark list` unchanged (still 12 cases — benchmark dataset
untouched). Collector manually demonstrated against one assertion synthetic case, one import
synthetic case, and one reconstructed real case.

**Explicitly not claimed**: that Collector's context-selection is exhaustive or complete (see
the stated rule-3 limitation above); that the retrieval-completeness diagnostic
(`docs/research_protocol.md` unresolved item 12) is now resolved — Collector existing doesn't
resolve the measurement-methodology question, which remains deferred. No Diagnoser, Patcher,
Validator, Gatekeeper, or Orchestrator code was added. No LLM SDK was added. No GitHub API
integration was added. No benchmark case was added, modified, or removed.

## 2026-09-19 — Phase 3 audit: evaluator-only retrieval-completeness diagnostic added

Before freezing Phase 3, added a small observability layer so a future diagnosis failure can
be separated from a Collector/context-retrieval failure — `src/renacir/evaluation/retrieval.py`,
deliberately a new top-level package **outside** `renacir.collector` (nothing in Collector
imports it; nothing in it is reachable from `collect()`). The context-selection algorithm
itself (traceback-referenced files → failing test file → single-hop local imports, for
original-fixture cases only) is unchanged — this step measures that policy, it does not modify
it. No embeddings, search, RAG, or transitive traversal was added or considered for addition.

**`RetrievalDiagnostic`** (evaluator-only; not part of `ModelFacingContext`, not part of
`CollectorOutput`): `selected_file_count`/`_total_chars`/`_total_lines`, `selection_reasons`
(count per reason), `empty_context`, `truncation_occurred`, plus
`reference_relevant_files_available/_retrieved/_total` and `reference_relevant_file_recall` —
computed by comparing `selected_context`'s paths against `reference_relevant_files(case)`: a
real case's already-recorded `upstream.production_files`, or a synthetic case's `+++ b/<path>`
diff headers parsed from the stored `fix.patch`. `None` (never a fabricated `False`/`0`) when
no file list can be derived.

**Leakage-independence, proven not just asserted**: `compute_retrieval_diagnostic` is called
strictly *after* `collect()` returns and is read-only with respect to its `CollectorOutput`
argument. `tests/evaluation/test_retrieval.py::test_reference_relevance_cannot_influence_collection`
scores the *same* already-produced `CollectorOutput` against two maximally different
reference-file answers (a case's real reference set vs. `None`, via an empty benchmark root)
and confirms the output is byte-for-byte unchanged by either call, then re-runs `collect()`
independently and confirms it reproduces the identical result — evaluator knowledge can score
retrieval after the fact but cannot feed back into it.

**A factual correction to Phase 3's own `docs/collector.md`, found while building this**: an
earlier draft called `helpers.py` "the most diagnostically relevant file" for
`import-renamed-helper` without distinguishing "where the bug's root cause lives" from "what
the historical repair actually touches." Checked directly against `reference/fix.patch`: the
repair modifies only `main.py`'s import statement; `helpers.py` is never itself touched. Under
the diagnostic's strict repair-touched-files definition, this case therefore shows **complete**
recall (`main.py` is both the only reference-relevant file and already selected via the
traceback rule) — not the incomplete recall the single-hop limitation might suggest. This is
reported as measured, not adjusted to match the earlier (imprecise) framing:

| Case | selected files | reference-relevant files | retrieved | recall | empty_context |
|---|---|---|---|---|---|
| `assertion-average-off-by-one` | `test_stats.py`, `stats.py` | `stats.py` | 1/1 | 1.0 | false |
| `import-renamed-helper` | `test_main.py`, `main.py` | `main.py` | 1/1 | **1.0** (corrected from an assumed "incomplete") | false |
| `httpie-custom-host-header` | *(none)* | `httpie/models.py` | 0/1 | **0.0** | **true** |

Both the 1.0 and 0.0 results are kept exactly as measured, per the explicit instruction not to
adjust the algorithm to make scores look better either way. `httpie-custom-host-header`'s zero
recall reflects a real, already-documented property: its only traceback frame is the withheld
retrospective test overlay, so rule 1 finds nothing selectable and rules 2/3 don't run at all
for a reconstructed case.

**Also tested**: a constructed no-applicable-metadata case (`reference_relevant_files_available:
false`, all three dependent fields `None`, not a fabricated zero) and truncation accounting
(`truncation_occurred: true` under an artificially tight `max_lines_per_file`) — both via
`tests/evaluation/test_retrieval.py`, 7 tests total.

**Verified before considering this audit step complete**: full `pytest` suite (240 passed —
233 prior + 7 new) and unrestricted `pytest .` both pass; `ruff check .` and
`ruff format --check .` clean; `git diff --check` clean; `python -m renacir.benchmark list`
unchanged (still 12 cases). The three re-run CLI demonstrations
(`assertion-average-off-by-one`, `import-renamed-helper`, `httpie-custom-host-header`) produce
`selected_context`/`stdout`/`stderr`/`parsed_failure` identical to the pre-audit Phase 3
report, with the diagnostic printed as clearly-labeled additional output, never replacing or
altering the existing fields.

**Documentation**: `docs/collector.md` gained the diagnostic's contract, the `helpers.py`
correction above, and an explicit "what this is not" statement (not a claim about the only
relevant files, not semantic relevance, not a diagnosis-success predictor).
`docs/research_protocol.md`'s unresolved item 12 updated from "deferred until Collector is
implemented" to "narrowed" — the per-case measurement now exists; the aggregation/reporting
policy across the benchmark remains open, not decided by this entry.

**Explicitly not claimed**: that recall is a proxy for semantic relevance, that 1.0 recall
predicts diagnosis success, or that 0.0 recall predicts failure. No change to
context-selection rules, limits, or defaults. No Diagnoser, Patcher, Validator, Gatekeeper, or
Orchestrator code was added. No LLM SDK, embeddings, search, or RAG dependency was added. No
benchmark case was added, modified, or removed.

## 2026-09-19 — Phase 4A design approved (with corrections); Phase 4B Diagnoser core implemented offline

**Phase 4A** was a design-only proposal for the first LLM-based component, the Diagnoser —
reviewed and approved with three corrections before any code was written:

1. **`category` (benchmark taxonomy metadata) removed from all model-visible input.** The
   Phase 4A proposal had included it on the grounds that it's redundant with
   `parsed_failure.error_type`; the correction holds that "redundant with something
   legitimate" is not the same as "legitimate," and a real CI failure would never arrive
   pre-labeled with its own taxonomy category. Removed from `DiagnoserInput` and the rendered
   prompt entirely; the model must infer failure type from execution evidence alone.
2. **No generic `llm_api_key` setting.** Provider-specific secrets (e.g. `ANTHROPIC_API_KEY`)
   belong to a future concrete provider adapter, never to the provider-neutral core.
3. **No real provider this phase.** Only the `LLMProvider` interface and a `FakeProvider` are
   implemented — no SDK installed, no network call, pending a full prompt/boundary audit first.

**Phase 4B implements exactly the corrected design**, offline: `src/renacir/diagnoser/`
(`models.py`, `provider.py`, `providers/fake.py`, `prompts/v1.py`, `diagnoser.py`) and
`src/renacir/evaluation/diagnosis.py` (automated evaluation helpers, mirroring
`renacir.evaluation.retrieval`'s existing after-the-fact, evaluator-only posture).

**The pipeline implemented**: `CollectorOutput` → `DiagnoserInput` (explicit allowlist,
`build_diagnoser_input()`, which takes only a `CollectorOutput` and a condition string, never
a `BenchmarkCase` — a deliberate defense-in-depth choice so the module structurally cannot
read `reference_repair`/`independent_checks`/`upstream`/`curation`/`test_overlay` even by
accident) → versioned rendered prompt (`diagnoser-v1`) → `LLMProvider.generate()` (called
exactly once, no retry, no "repair the JSON with another call") → strict `Diagnosis` parsing/
validation (Pydantic-enforced bounds: confidence in `[0.0, 1.0]`, capped list lengths and
string lengths — an out-of-bounds or malformed response is recorded as `parse_status`
`"validation_error"`/`"parse_error"`, never silently accepted or truncated) → grounding check
→ `DiagnosisRunRecord`.

**`diagnosis_confidence` semantics, stated explicitly, not left implicit**: a self-reported,
uncalibrated belief score — not `P(correct)`, not used by any decision logic (there is no
Gatekeeper), recorded only as a future candidate signal per `docs/research_protocol.md` §9's
B2 baseline. Directly grounded in Fisch et al.'s risk-coverage-vs-calibration distinction
(`docs/literature_review.md` §3, already vetted).

**`insufficient_context` is first-class**, not inferred from low confidence, and is never set
automatically from `RetrievalDiagnostic` — that decision belongs to the model based only on
what it was actually shown. Proven, not just documented:
`tests/diagnoser/test_diagnoser_leakage.py::test_retrieval_diagnostic_computation_cannot_alter_diagnoser_input`
computes a `RetrievalDiagnostic` between two `build_diagnoser_input()` calls on the same
`CollectorOutput` and confirms both produce an identical result.

**Grounding**: `suspected_files` checked against every path the model actually saw (selected
context, traceback frames, bare repository-structure filenames); a citation outside that set
is recorded as `grounding_violation`, never silently dropped or used to discard the model's
output. **`suspected_symbols` grounding is deliberately not implemented** — reliably verifying
a free-text symbol name against visible source would require either real AST-level parsing or
a substring search prone to false positives/negatives, exactly the "invented brittle
validator" this phase was told not to build. Recorded as a stated limitation in
`docs/diagnoser.md`, not silently patched over.

**Retrospective-overlay boundary carried through unchanged from Phase 3**: verified for all 3
real cases by building the *actual* `CollectorOutput` and *actual* rendered prompt (not a
synthetic stand-in) and confirming the overlay's literal source text is absent from both input
conditions —
`tests/diagnoser/test_diagnoser_leakage.py::test_real_case_retrospective_overlay_source_never_appears_in_prompt`.

**Two input conditions implemented as infrastructure, not run as an experiment**:
`failure_output_only` (selected context and repository structure forced empty) and
`full_context` (populated exactly as Collector produced them) — same prompt structure, output
schema, and provider configuration otherwise, so a later comparison isolates whether selected
source context adds measurable value.

**Discrepancy found and fixed during implementation**: two new test files
(`tests/diagnoser/test_models.py`, `tests/diagnoser/test_leakage.py`) collided by basename
with existing files in `tests/collector/` — this repository has no `__init__.py` in test
directories, so pytest's rootdir-relative module naming raised `import file mismatch` the
moment the full suite (not just `tests/diagnoser/`) was run. Fixed by renaming to
`test_diagnoser_models.py`/`test_diagnoser_leakage.py`, matching the only viable fix under the
existing no-`__init__.py` convention rather than introducing package markers project-wide.

**Verified before considering Phase 4B complete**: full `pytest` suite (331 passed — 240 prior
+ 91 new) and unrestricted `pytest .` both pass; `ruff check .` and `ruff format --check .`
clean; `git diff --check` clean; `pyproject.toml` unchanged (confirmed via diff); `import
anthropic`/`import openai` both fail (not installed); no network-library import anywhere in
`src/renacir/diagnoser/`. Three offline `FakeProvider` demonstrations run
(`assertion-average-off-by-one`/`full_context`, `import-renamed-helper`/`failure_output_only`,
`httpie-custom-host-header`/`full_context`) — the third confirms Phase 3's own empty
`selected_context` for that case is unchanged and correctly renders as `SOURCE_FILES: none
provided`. Benchmark manifest and fixtures, Collector selection behavior, and
`RetrievalDiagnostic` all confirmed unchanged.

**Explicitly not claimed**: any diagnosis accuracy, quality, or confidence-calibration result
— none exists, no real model has been called. No Patcher, Validator, Gatekeeper, or
Orchestrator code was added. No LLM SDK was installed. No new dependency was added
(`pyproject.toml` diff is empty). No API key was configured or required. K and its aggregation
rule remain exactly as unresolved as `docs/research_protocol.md` §14 already states — nothing
in `DiagnosisRunRecord` assumes or encodes a specific value.

## 2026-09-20 — Phase 4C: Anthropic adapter implemented and offline-verified; planned smoke call blocked, not skipped

**Discrepancy noted at the start of this phase, not silently absorbed**: this phase's
instructions stated "Phase 4B is complete and committed." `git log` shows the latest commit as
`b6612aa` ("Implement Phase 3 Collector and retrieval diagnostics") — Phase 4A/4B's Diagnoser
work (`src/renacir/diagnoser/`, `src/renacir/evaluation/diagnosis.py`, `docs/diagnoser.md`,
and the `ARCHITECTURE.md`/`README.md`/`docs/decisions.md`/`docs/research_protocol.md` edits
recorded in the prior entry) was present in the working tree but **uncommitted**. Proceeding
on the working tree as-is (uncommitted state is not lost or at risk, and this phase's own
instructions were "do not commit" regardless) rather than committing on the user's behalf
without being asked.

**Implemented**: the first real provider adapter, `AnthropicProvider`
(`src/renacir/diagnoser/providers/anthropic.py`), and a `python -m renacir diagnose` CLI
command (`src/renacir/__main__.py`). Added one dependency, `anthropic>=0.40` (the official
SDK) — the only dependency change this phase, exactly as authorized.

**A concrete, non-obvious finding**: the Anthropic SDK's client defaults to `max_retries=2`
internally — silent transport-level retries this project's own orchestration code would never
see. Given the explicit "exactly one model call means exactly one model call" requirement,
this had to be overridden to `max_retries=0` at client construction — otherwise "no retry"
would have held at the `renacir.diagnoser.diagnoser.diagnose()` call site while silently not
holding at the HTTP layer underneath it. Verified by inspecting the constructed client's own
`max_retries` attribute (`tests/diagnoser/test_anthropic_provider.py`), not merely assumed
from reading the constructor signature.

**Secrets handling, verified not just designed**: `AnthropicProvider` takes its API key as a
plain constructor argument and never reads `os.environ` itself (kept fully unit-testable
without touching real configuration). The CLI resolves the key from
`renacir.config.Settings.anthropic_api_key` (new field, sourced from the `ANTHROPIC_API_KEY`
environment variable / `.env`, following the project's existing `pydantic-settings` pattern —
no parallel secret-loading mechanism introduced) — never a CLI argument. `.env.example` gained
`ANTHROPIC_API_KEY=` and `LLM_MODEL=` with no real values. A planted fake-secret string was
confirmed absent from a full `DiagnosisRunRecord`'s serialized JSON (rendered prompts,
fingerprint, every field) and from CLI stdout/stderr on every refusal path, not just asserted
by design.

**Model identifier**: never given a code-level default anywhere — `Settings.llm_model` is
`None` by default, `--model` has no CLI default, and the CLI refuses cleanly if neither is
set, before touching the provider or any secret.

**CLI safety gate**: `--allow-api-call` is required before the command will resolve the API
key, construct a provider, or reach the network at all; its absence is checked before the
model-id check's *sibling* concerns (key resolution, provider construction) so a run with
neither flag correctly reports the API-call refusal first. Tested directly, not just by code
inspection.

**Offline verification completed** (`tests/diagnoser/test_anthropic_provider.py`,
`tests/test_diagnose_cli.py`, plus a full re-run of every Phase 4B leakage test): request-field
mapping to the Anthropic Messages API, text/token-usage extraction, latency recording,
`APIError`-to-`provider_error` mapping without raising, exactly-one-call-on-error, non-`APIError`
exceptions still propagating (never misreported as a provider failure), `max_retries=0`
confirmed on the real client, missing-API-key / missing-model / missing-`--allow-api-call` /
unknown-case-id all refused cleanly with no secret ever printed. Full `pytest`/`pytest .`
(347 passed), `ruff check .`, `ruff format --check .`, and `git diff --check` all clean.
`import anthropic` now succeeds (expected — it's the newly added dependency); no other new
package appeared in the dependency tree beyond `anthropic`'s own transitive requirements.

**The planned single real smoke call was NOT made this session — blocked on two required
inputs neither this document nor this session may supply**:
1. `ANTHROPIC_API_KEY` is not set in this environment (confirmed via direct check before any
   implementation work began).
2. No exact Anthropic model identifier was supplied — by explicit design (this entry and
   `docs/diagnoser.md`), the code never defaults or guesses one, and choosing one is reserved
   for the user, not inferred here.

This is reported as a blocked step, not silently worked around by picking a plausible-looking
model string or reading a key from somewhere unexpected. **No real API call has been made. No
diagnosis, accuracy, or calibration result exists from this phase.** The actual smoke-call
procedure (exact CLI invocation, pre-call metadata to report, post-call fields to report, the
prompt-freeze rule) is otherwise fully ready to execute once both inputs are supplied.

**Explicitly not claimed**: any diagnosis result, any accuracy/calibration finding, that
`diagnoser-v1` was validated against a real model in any way. Prompt v1 was not edited. No
Patcher, Validator, Gatekeeper, or Orchestrator code was added. No dependency beyond
`anthropic` was added. No benchmark case, manifest entry, or fixture was touched. Collector
and `RetrievalDiagnostic` behavior unchanged (no test in either area was modified, only
re-run).
