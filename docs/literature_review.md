# Literature Review — Phase 1.6 Checkpoint

**Status: checkpoint complete — 2026-09-18.** This is a targeted literature checkpoint against
the specific unresolved questions in `docs/research_protocol.md`, not a general survey of AI
code repair. It records what the cited literature actually establishes, what Renacir infers
from it, and the limits of that inference — kept as three separate things throughout, per
`docs/research_protocol.md`'s own standard for citation honesty.

Every claim below is sourced from a paper either **read in full** this checkpoint or verified
at **metadata/abstract level only**; the two are marked explicitly per section, and
metadata-only sources are never used as the sole support for a decision that changed the
protocol (see §9). Sources already vetted in `docs/decisions.md`'s earlier literature
checkpoint (dated 2026-09-17) are cited here only as background/framing, not re-verified in
this pass unless stated.

## 1. Purpose and scope

This checkpoint exists to answer, with evidence rather than assumption, a specific set of
methodological questions left open when `docs/research_protocol.md` was frozen: whether
naive ECE is usable at Renacir's expected scale, whether any conformal-prediction method's
assumptions map onto Renacir's repository-clustered structure, how "correctness beyond the
originally-failing test" should be operationalized, what contamination risk real historical
cases carry, and whether the protocol's proposed statistical tools (Clopper-Pearson,
McNemar, cluster bootstrap) are defensible at n≈30–50. It does not attempt to survey AI code
repair broadly, and it does not select the final Gatekeeper algorithm — per
`docs/research_protocol.md` §9, that remains explicitly out of scope until baselines B1–B3
are built.

## 2. Automated program repair and patch correctness

**What the literature establishes:**

Qi, Long, Achour & Rinard (ISSTA 2015) — read in full — distinguish a *plausible* patch
(passes the provided test suite) from a *correct* one (fixes the bug without introducing new
ones), and show, via manual inspection combined with developer-intent analysis, that a
substantial share of plausible patches from generate-and-validate repair systems are not
actually correct.

Smith, Barr, Le Goues & Brun (ESEC/FSE 2015) — confirmed via secondary source, not the
primary PDF — make the same point independently: repairing and evaluating correctness with
the same test set cannot distinguish a correct fix from one that overfits the visible tests.
Their evaluation used an independently-generated (KLEE-based) white-box test suite, separate
from the training test suite, as an additional correctness check.

SWT-Bench (Mündler, Müller, He & Vechev, NeurIPS 2024) — read in full — validates generated
tests using the gold patch as ground truth via differential (fail→pass) execution, not a
held-out set, and explicitly reports that generated tests sometimes still pass an *incorrect*
patch (Table 5 of the paper: success rate for an incorrect-but-applicable patch matched the
golden-patch condition on one configuration tested).

PatchDiff (Wang, Pradel & Liu, arXiv 2503.15223, accepted ICSE 2026) — read in full —
generates LLM-synthesized tests that behaviorally differentiate a candidate patch from an
oracle patch. On SWE-bench-style tasks, 29.6% of "plausible" (test-passing) patches were
differentiable from their oracle. Critically, a manual follow-up audit of 77 sampled
differentiable patches found only 28.6% definitively incorrect, 5.2% correct *despite*
divergence, and 66.2% of genuinely uncertain correctness — the paper's own words: "A
behavioral discrepancy reveals incorrectness only when the behavior of the generated patch
violates the expected behavior," and it documents a specific case (a matplotlib pickle-
handling patch) where a divergent implementation was still defensible.

**What Renacir infers:**

This is direct, multi-source, decade-spanning evidence that test-suite passage is
insufficient for correctness — supporting `docs/research_protocol.md` §7's existing
tier-1/tier-2/incorrect taxonomy. PatchDiff's own uncertain-majority finding (66.2%) is read
here as empirical validation that a "plausible but not established correct" tier is the
*expected* common case, not an edge case the taxonomy over-engineers for. The matplotlib
example is read as direct support for the protocol's existing rule that correctness never
requires syntactic/structural similarity to the gold patch.

**Limitation of this inference:** none of these four papers were run on Renacir's own
benchmark or failure classes (assertion/import errors specifically); the finding that
divergence-is-common transfers by analogy from SWE-bench-scale, heterogeneous-bug corpora,
not by direct measurement on Renacir's cases.

## 3. Selective prediction and abstention

**What the literature establishes:**

Geifman & El-Yaniv (NeurIPS 2017, arXiv 1705.08500) — read in full — formally define
coverage as `E_P[g(x)]` and selective risk as `E_P[ℓ(f(x),y)g(x)]/E_P[g(x)]`, and construct
the risk-coverage curve by sweeping a confidence threshold. Their guarantees (Theorem 3.2)
are stated as probabilistic bounds on selective risk, not confidence intervals on point
estimates, and the paper gives no explicit minimum-sample-size guidance — its own empirical
validation uses thousands of held-out points (≈5,000–25,000).

Fisch, Jaakkola & Barzilay ("Calibrated Selective Classification," TMLR, arXiv 2208.12084) —
read in full — argue plain risk-coverage optimization (à la Geifman & El-Yaniv) can select a
confidence-maximizing rejection rule while the underlying confidence *scores* remain
uncalibrated, meaning accuracy-at-a-coverage-level can look good while the stated uncertainty
is still misleading. Their proposed fix (a separately-trained selector network minimizing a
calibration-specific loss) is explicitly reported as needing "a relatively small subset of
held-out examples (e.g., ≈10³)" to train.

**What Renacir infers:**

The risk-coverage framework (§10.1–10.3 of the protocol) is directly grounded in Geifman &
El-Yaniv's original formalization, confirming it as an appropriate primary evaluation
artifact for a selective-prediction study. Fisch et al.'s distinction — that a good
risk-coverage curve does not by itself prove the underlying confidence scores are calibrated
— is read as the reason the protocol treats calibration (§10.7–10.8) as a *separate*,
secondary analysis rather than assuming risk-coverage performance implies calibration.

**Limitation of this inference:** Fisch et al.'s own proposed remedy requires ~10³ held-out
examples to train a separate selector network — one to two orders of magnitude beyond
Renacir's expected 30–50 cases. Their *diagnosis* (risk-coverage ≠ calibration) transfers;
their *proposed method* does not, at this scale. Renacir cannot adopt selective calibration
as specified in this paper.

## 4. Confidence calibration

**What the literature establishes:**

Guo, Pleiss, Sun & Weinberger ("On Calibration of Modern Neural Networks," ICML 2017) — read
in full — define Expected Calibration Error as `ECE = Σ_m (|B_m|/n)|acc(B_m) − conf(B_m)|`
over equal-width bins, and note the Brier score (`(1/n)Σ(ŷ_i−y_i)²`) as a related but
distinct metric; the paper does not give explicit sample-size guidance for reliable ECE
estimation.

Kumar, Liang & Ma ("Verified Uncertainty Calibration," NeurIPS 2019, Spotlight) — read in
full — show histogram-binning-based calibration error estimation requires **O(B/ε²)** samples
(B = number of bins, ε = target precision) versus O(1/ε²) for their proposed scaling-based
alternative. Concretely, for B=10 bins at ε=0.05, this is on the order of 4,000 samples.

Roelofs, Cain, Shlens & Mozer ("Mitigating Bias in Calibration Error Estimation," AISTATS
2022, arXiv 2012.08668) — read in full — show equal-mass binning has lower estimation bias
than equal-width binning, and quantify the practical consequence: reliably detecting 2%
miscalibration requires over 10,000 samples, and below 500 samples only miscalibration
exceeding roughly 10% can be reliably detected at all.

**What Renacir infers:**

At n≈30–50, naive (equal-width, small-B) histogram-binning ECE is not a statistically
defensible scalar — both papers, independently, put the sample requirements one to three
orders of magnitude above Renacir's expected benchmark size. This is a direct,
full-text-verified finding, not an extrapolation.

**Limitation of this inference:** neither paper establishes that the *Brier score* is
sufficient at n≈30–50, only that it avoids the specific binning-driven sample-complexity
problem ECE has. Nor do they address calibration estimation under repository-clustered
(non-i.i.d.) observations — both analyses assume i.i.d. samples. Whether Brier score alone,
or no scalar calibration summary at all, is the right choice for Renacir remains open (see
§9).

Background, not independently re-verified this pass: Kadavath et al. (arXiv 2207.05221,
already vetted 2026-09-17) on LLM self-reported confidence calibration in NLP settings; "Code
Is More Than Text" and "Functional Entropy" (already vetted 2026-09-17) arguing NLP-derived
calibration/uncertainty methods transfer poorly to code. These inform why the protocol
(§2, §21) refuses to assume Diagnoser/Patcher self-reported confidence is calibrated for
code without in-benchmark validation — a framing point, not re-verified with a full read this
checkpoint.

## 5. Conformal prediction

**What the literature establishes:**

Angelopoulos & Bates ("A Gentle Introduction to Conformal Prediction...," originally arXiv
2107.07511, subsequently published as *Conformal Prediction: A Gentle Introduction*,
Foundations and Trends in Machine Learning, vol. 16, 2023, pp. 494–591) — read in full —
state the core exchangeability requirement formally (calibration and test points i.i.d., or
more generally exchangeable) and note that under unknown violations of exchangeability the
coverage guarantee is not formally analyzed in the tutorial itself; grouped/hierarchical data
structures are not addressed.

Barber, Candès, Ramdas & Tibshirani ("Predictive Inference with the Jackknife+," Annals of
Statistics 49(1), 2021, DOI 10.1214/20-AOS1965, arXiv 1905.02928) — read in full — prove a
≥1−2α coverage guarantee under exchangeability of the n+1 data points and a *symmetric*
fitting algorithm, and **explicitly state their method does not address clustered or grouped
data**, noting correlated within-group observations "would violate exchangeability and
symmetry, likely invalidating theoretical guarantees."

Barber, Candès, Ramdas & Tibshirani ("Conformal Prediction Beyond Exchangeability," Annals of
Statistics 51(2), 2023, arXiv 2202.13415) — read in full — target *temporal distribution
drift* specifically (their examples: electricity demand, election-reporting order), proving a
bounded-degradation result (coverage gap bounded by a total-variation term) under weighted
quantiles. The paper explicitly does **not** address grouped observations sharing a discrete
group identity (e.g., "multiple patients from the same hospital") — confirmed by direct
reading, not inference from the title.

Oliveira, Orenstein, Ramos & Romano ("Split Conformal Prediction and Non-Exchangeable Data,"
JMLR 25, 2024, pp. 1–38) — content fetched and confirmed this checkpoint (not a full
line-by-line read) — targets the same temporal/spatiotemporal dependence family as the paper
above, via concentration inequalities and decoupling; does not discuss discrete-group
observations.

Ding, Angelopoulos, Bates, Jordan & Tibshirani ("Class-Conditional Conformal Prediction with
Many Classes," NeurIPS 2023, arXiv 2306.09335) — verified at abstract/metadata level only,
not full-read — proposes *clustered conformal prediction*: clustering **prediction classes**
with similar conformal scores and calibrating at the cluster level, to address too few
labeled calibration examples per class.

Vovk, Lindsay, Nouretdinov & Gammerman ("Mondrian Confidence Machine," Royal Holloway
technical report, 2003) — verified to exist, unpublished, metadata-level only — is the
origin of group-conditional conformal prediction (partition calibration data by a group
variable, conformal-predict within each group); its own known failure mode is degraded
performance when a group has too few examples.

**What Renacir infers — with an explicit, deliberately non-conflating mapping:**

None of these four candidate families has been shown, by the sources actually read, to solve
Renacir's specific problem: cases grouped by source repository, where within-repo cases may
be dependent (shared style, shared bug patterns) but the number of repositories and
cases-per-repository is small and not yet known. Specifically:

- Jackknife+/CV+'s own stated assumptions (full-text-confirmed) explicitly exclude grouped
  data.
- The two "beyond exchangeability" papers (full-text and content-fetch confirmed) both target
  *temporal* drift, not discrete-group dependence — a different mechanism entirely, despite
  superficially relevant framing ("non-exchangeable").
- Class-conditional/clustered conformal prediction (Ding et al.) clusters **classes with too
  few labeled examples**, not **source-groups with potential within-group dependence** — a
  different statistical problem that happens to share the word "clustered."
- Mondrian conformal prediction is the structurally closest match (partition by a discrete
  group variable) but is an unpublished report whose own known limitation — degraded
  performance at low per-group counts — is exactly the regime most of Renacir's repositories
  would likely fall into.

**This is treated as a genuine negative finding, not an oversight**: no conformal method
currently examined has literature-established applicability to Renacir's repository-grouped,
small-n, stochastic-output setting. Per `docs/research_protocol.md` §9, no method is selected
on this basis, and none should be — this checkpoint does not force a conformal method into
the project.

## 6. Benchmark construction and contamination

**What the literature establishes:**

SWE-bench (Jimenez et al., ICLR 2024, arXiv 2310.06770) — read in full — filters ~90,000 PRs
down to 2,294 instances via a three-stage pipeline (repo selection, issue/test-change
filtering, execution-based fail→pass filtering), draws from only 12 repositories with highly
uneven distribution (Django alone: 850 of 2,294 instances, ≈37%), and reports its own
internal contamination check (performance split by pre/post-2023 PR date) found "little
difference," concluding models are "unlikely to cheat."

BugsInPy (Widyasari et al., ESEC/FSE 2020, arXiv 2401.15481) — read in full — validated 493
bugs across 17 Python projects via a dual-independent-reviewer process (of 796 candidates,
303 were rejected), each bug isolating a failing test and an isolated fix commit.

The SWE-Bench Illusion (Liang, Garg & Zilouchian Moghaddam, arXiv 2506.12286, preprint, not
peer-reviewed) — read in full — uses diagnostic tasks (identify buggy file paths, reproduce
removed functions, complete code prefixes) with *no repository access*, finding models score
markedly higher on SWE-Bench-Verified (up to 76% file-path accuracy) than on external/
outside-repo tasks (<53%), consistent across ten models. The paper's own framing: this
reveals "suspicious performance patterns...rather than direct proof" of memorization.

SWE-rebench (Badertdinov et al., NeurIPS 2025 Datasets & Benchmarks Track, arXiv 2505.20411)
— read in full — reports DeepSeek-V3 scoring 39.7% on SWE-bench Verified versus 21.3% on
contemporaneous fresh SWE-rebench tasks (an 18.4-point gap on the same model), and recommends
tracking issue/PR dates against model release dates, continuous fresh-task collection, and
running 5+ trials with reported standard error.

**What Renacir infers:**

Three findings, tiered by evidentiary strength per `docs/research_protocol.md`'s own
requirement not to conflate direct proof with diagnostic evidence:

- *Direct evidence*: none available for any specific case or model — and none of the papers
  above claim otherwise.
- *Diagnostic evidence consistent with memorization*: the no-repo-context accuracy gaps (SWE-
  Bench Illusion) and the same-model old-vs-fresh-benchmark performance gap (SWE-rebench,
  21.3 vs. 39.7 points) both constitute this tier — real, converging, but not proof for any
  individual instance.
- A *methodological lesson*, not just a contamination finding: SWE-bench's own coarse
  temporal-partition check found nothing, while later, more targeted diagnostic methods found
  what it missed — coarse date-partitioning alone is an insufficient contamination test.

For Renacir's own real-case sourcing (§11 of the protocol): BugsInPy is a rigorously
validated, ready-to-use candidate source, but **its popularity as a well-known 2020 academic
benchmark plausibly puts it in the same training-data-representation risk class as
SWE-bench** — no paper checked BugsInPy for contamination specifically, and being smaller or
Python-specific does not exempt it from the same mechanism (a well-known, widely-discussed
dataset is more, not less, likely to be represented in a large model's training corpus).

**Limitation of this inference:** the diagnostic techniques (no-context file-path
identification, etc.) were built for SWE-bench-scale, GitHub-issue-style tasks; whether they
would even be informative on Renacir's much narrower failure classes (assertion/import
errors) has not been tested by anyone, including this checkpoint.

## 7. Statistical analysis

**What the literature establishes:**

Clopper & Pearson (Biometrika 26(4), 1934, DOI 10.1093/biomet/26.4.404) is the standard exact
binomial confidence interval construction; validity does not depend on sample size the way
normal-approximation intervals do. This is a closed-form mathematical result, not an
empirical claim requiring a full re-read to verify.

McNemar (Psychometrika 12, 1947, DOI 10.1007/BF02295996) established the standard test for
paired binary outcomes on the same subjects.

Dietterich ("Approximate Statistical Tests for Comparing Supervised Classification Learning
Algorithms," Neural Computation 10(7), 1998) — confirmed via a detailed secondary source
(lecture notes), not the primary text directly (paywalled) — recommends McNemar's test for
comparing two classifiers on one shared test set, and separately found two other common tests
(including a naive difference-of-proportions test) have unacceptably high false-positive
rates for this purpose.

MacKinnon & Webb ("The Wild Bootstrap for Few (Treated) Clusters," The Econometrics Journal
21(2), 2018, pp. 114–135, DOI 10.1111/ectj.12107) — verified to exist with this exact
citation, metadata-level only — shows wild cluster bootstrap methods remain reliable in
cluster-robust *regression* inference even with very few treated clusters, recommending Webb
weights at the smallest cluster counts.

Cameron, Gelbach & Miller ("Bootstrap-Based Improvements for Inference with Clustered
Errors," Review of Economics and Statistics 90(3), 2008, pp. 414–427) — metadata/abstract
level only — states cluster-robust standard errors presume "a large number of clusters" and
that standard asymptotic tests over-reject with few (5–30) clusters.

Zhou, Van Landeghem, Popordanoska & Blaschko ("A Novel Characterization of the Population
AURC and Rates of Finite Sample Estimators," ICML 2025, arXiv 2410.15361) — verified to
exist with this exact citation and venue (ICML 2025 poster), metadata-level only — proves
finite-sample AURC plug-in estimators are consistent, low-bias, with MSE converging at rate
O(√(ln(n)/n)).

**What Renacir infers:**

Clopper-Pearson remains appropriate for descriptive binomial intervals *where the
independence assumption holds* — but that qualifier is now explicit: it does not, by itself,
account for repository clustering. If cases from the same repository are correlated, a
Clopper-Pearson interval computed on the pooled case-level proportion will understate true
uncertainty exactly the way naive cluster-robust standard errors do in Cameron/Gelbach/
Miller's finding. This limitation is the same open problem as repository-clustered
uncertainty generally (§9 below) — Clopper-Pearson is not a solution to it, only a correct
tool for the unclustered part of the estimate.

McNemar's test is a reasonable starting point for paired same-test-set comparisons (per
Dietterich, at unclustered-pairs granularity); whether it needs a clustering correction for
repo-grouped cases is a genuinely open question — no source was found addressing McNemar
under within-cluster correlation of the paired observations specifically.

MacKinnon & Webb's finding is read as a *promising lead*, not a validated solution: the
small-cluster-count problem it solves is structurally similar to Renacir's (few clusters),
but the actual statistical setting — regression treatment-effect inference on a continuous or
count outcome — is not the same as Renacir's proportion/paired-binary-outcome setting. This
paper has not been read in full and its machinery has not been shown to transfer.

Zhou et al.'s AURC result is read the same way: real and on-point, but its formal convergence
rate is loose at Renacir's scale. As an illustration (a calculation performed for this
checkpoint, not stated by the paper): at n=30, √(ln(30)/30) ≈ 0.34 — a wide bound, suggesting
substantial residual finite-sample uncertainty remains at Renacir's expected n even though
the estimator is asymptotically consistent. This supports keeping AURC secondary (as already
frozen in `docs/research_protocol.md` §10.4), not changing that status, and does not resolve
how to attach a usable uncertainty figure to a reported AURC number.

**Limitation of this inference, generally**: three of the five statistics sources above
(MacKinnon & Webb, Cameron/Gelbach/Miller, Zhou et al.) are metadata-verified only. None of
their specific formulas or theorems have been independently confirmed by a full read in this
checkpoint, and none should be treated as settling a Renacir design choice on their own.

## 8. Implications for Renacir

Collected across §2–§7, the clearest pattern in this checkpoint is that Renacir's existing
protocol design choices are, where checked, either directly supported (the tier-1/tier-2/
incorrect correctness taxonomy, the risk-coverage-first evaluation framework, Clopper-Pearson
for unclustered proportions) or correctly left open because no literature-validated answer
exists yet (conformal method choice, repo-split scheme, calibration-summary metric beyond
ruling out naive ECE, clustered-uncertainty estimation generally). No finding in this
checkpoint requires walking back a frozen design decision — several strengthen ones already
made, and a few narrow what remains open without resolving it.

## 9. Decisions supported by the literature

These four are treated as evidence-sufficient and are the basis for the protocol edits
applied alongside this document (see `docs/decisions.md`'s dated entry for the change log):

1. **Reject naive equal-width histogram-binning ECE** as the primary scalar calibration
   summary at Renacir's expected n≈30–50 — full-text support from Kumar, Liang & Ma (2019)
   and Roelofs et al. (2022), both quantifying sample requirements one to three orders of
   magnitude beyond Renacir's scale.
2. **Confirm (not revise) the existing correctness taxonomy** — full-text support from Qi et
   al. (2015), SWT-Bench (2024), and PatchDiff (2025/2026), converging on: test-suite passage
   is necessary but insufficient for correctness, and divergence from a gold patch is not by
   itself evidence of incorrectness.
3. **Retain Clopper-Pearson for unclustered binomial proportions**, with the explicit new
   caveat that it does not address repository clustering — a closed-form mathematical result
   requiring no further verification, now stated with its precise scope.
4. **Adopt a concrete contamination-mitigation policy** for real-case sourcing — full-text
   support from SWE-rebench, SWE-Bench Illusion, and SWE-bench's own internal (insufficient)
   check, converging on: track dates against training cutoffs, never claim proof of absence,
   don't exempt popular curated datasets from the same risk class as SWE-bench.

## 10. Questions intentionally left unresolved

Per `docs/research_protocol.md`'s own standard, treating a question as unresolved is a
recorded decision, not an oversight. This checkpoint leaves the following open, with reasons:

- **Brier score vs. no scalar calibration summary at all** — ruling out naive ECE does not by
  itself establish Brier is sufficient at this n, nor address clustered-observation
  calibration.
- **Calibration-uncertainty representation method** — no small-n-appropriate method found.
- **Repository-level split scheme** (LORO vs. grouped k-fold vs. fixed) — contingent on real
  repo/case counts not yet known.
- **Diagnosis-accuracy metric's exact granularity** (line vs. function level) — Top-N
  confirmed as standard practice; exact choice not resolved.
- **Collector retrieval-completeness metric** — inherently deferred; Collector doesn't exist.
- **Whether conformal prediction will ultimately be used, and if so which family** — see §5;
  a genuine, literature-grounded negative finding, not a gap in search effort.
- **K (repeated stochastic runs) and the aggregation policy** — SWE-rebench's practice
  (K≥5, report SE/pass@N) is a directional anchor from a much larger-scale, differently-
  resourced benchmark, not a validated number for Renacir.
- **Real:synthetic benchmark ratio** — a resourcing decision; feasibility of real-case
  sourcing is now better evidenced (BugsInPy, SWE-bench), the target mix is not.
- **Clustered paired-comparison method** — McNemar's applicability under within-repo
  correlation of paired cases has no literature support found either way.
- **Repository-clustered uncertainty estimation, generally** — MacKinnon & Webb is a lead,
  not a validated method; its regression setting has not been shown applicable to Renacir's
  proportion/paired-binary setting.
- **AURC's precise finite-sample uncertainty at n≈30–50** — Zhou et al. establish asymptotic
  consistency; a usable finite-sample uncertainty figure at Renacir's exact scale has not been
  derived or confirmed here.

## 11. References

### Full-read this checkpoint

- Qi, Z., Long, F., Achour, S., Rinard, M. "An Analysis of Patch Plausibility and Correctness
  for Generate-And-Validate Patch Generation Systems." ISSTA 2015.
- Mündler, N., Müller, M.N., He, J., Vechev, M. "SWT-Bench: Testing and Validating Real-World
  Bug-Fixes with Code Agents." NeurIPS 2024. arXiv:2406.12952.
- Wang, Y., Pradel, M., Liu, Z. "Are 'Solved Issues' in SWE-bench Really Solved Correctly? An
  Empirical Study." arXiv:2503.15223 (accepted ICSE 2026).
- Geifman, Y., El-Yaniv, R. "Selective Classification for Deep Neural Networks." NeurIPS 2017.
  arXiv:1705.08500.
- Fisch, A., Jaakkola, T., Barzilay, R. "Calibrated Selective Classification." TMLR.
  arXiv:2208.12084.
- Guo, C., Pleiss, G., Sun, Y., Weinberger, K.Q. "On Calibration of Modern Neural Networks."
  ICML 2017.
- Kumar, A., Liang, P., Ma, T. "Verified Uncertainty Calibration." NeurIPS 2019.
- Roelofs, R., Cain, N., Shlens, J., Mozer, M.C. "Mitigating Bias in Calibration Error
  Estimation." AISTATS 2022. PMLR v151:4036–4054. arXiv:2012.08668.
- Angelopoulos, A.N., Bates, S. "Conformal Prediction: A Gentle Introduction." Foundations
  and Trends in Machine Learning, vol. 16, 2023, pp. 494–591. Originally arXiv:2107.07511.
- Barber, R.F., Candès, E.J., Ramdas, A., Tibshirani, R.J. "Predictive Inference with the
  Jackknife+." Annals of Statistics 49(1), 2021, pp. 486–507. DOI:10.1214/20-AOS1965.
  arXiv:1905.02928.
- Barber, R.F., Candès, E.J., Ramdas, A., Tibshirani, R.J. "Conformal Prediction Beyond
  Exchangeability." Annals of Statistics 51(2), 2023, pp. 816–845. arXiv:2202.13415.
- Widyasari, R., Sim, S.Q., Lok, C., et al. "BugsInPy: A Database of Existing Bugs in Python
  Programs to Enable Controlled Testing and Debugging Studies." ESEC/FSE 2020.
  arXiv:2401.15481.
- Jimenez, C.E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O., Narasimhan, K. "SWE-bench:
  Can Language Models Resolve Real-World GitHub Issues?" ICLR 2024. arXiv:2310.06770.
- Liang, S., Garg, S., Zilouchian Moghaddam, R. "The SWE-Bench Illusion: When State-of-the-Art
  LLMs Remember Instead of Reason." arXiv:2506.12286 (preprint, not peer-reviewed).
- Badertdinov, I., Golubev, A., Nekrashevich, M., Shevtsov, A., Karasik, S., Andriushchenko,
  A., Trofimova, M., Litvintseva, D., Yangel, B. "SWE-rebench: An Automated Pipeline for Task
  Collection and Decontaminated Evaluation of Software Engineering Agents." NeurIPS 2025,
  Datasets and Benchmarks Track. arXiv:2505.20411.

### Metadata/abstract-verified only (background; not sole support for any decision)

- Smith, E.K., Barr, E.T., Le Goues, C., Brun, Y. "Is the Cure Worse Than the Disease?
  Overfitting in Automated Program Repair." ESEC/FSE 2015. DOI:10.1145/2786805.2786825.
- Dietterich, T.G. "Approximate Statistical Tests for Comparing Supervised Classification
  Learning Algorithms." Neural Computation 10(7), 1998, pp. 1895–1923.
- Clopper, C.J., Pearson, E.S. "The Use of Confidence or Fiducial Limits Illustrated in the
  Case of the Binomial." Biometrika 26(4), 1934, pp. 404–413. DOI:10.1093/biomet/26.4.404.
- McNemar, Q. "Note on the Sampling Error of the Difference Between Correlated Proportions or
  Percentages." Psychometrika 12, 1947, pp. 153–157. DOI:10.1007/BF02295996.
- MacKinnon, J.G., Webb, M.D. "The Wild Bootstrap for Few (Treated) Clusters." The
  Econometrics Journal 21(2), 2018, pp. 114–135. DOI:10.1111/ectj.12107.
- Cameron, A.C., Gelbach, J.B., Miller, D.L. "Bootstrap-Based Improvements for Inference with
  Clustered Errors." Review of Economics and Statistics 90(3), 2008, pp. 414–427.
- Zhou, H., Van Landeghem, J., Popordanoska, T., Blaschko, M.B. "A Novel Characterization of
  the Population Area Under the Risk Coverage Curve (AURC) and Rates of Finite Sample
  Estimators." ICML 2025. arXiv:2410.15361.
- Oliveira, R.I., Orenstein, P., Ramos, T., Romano, J.V. "Split Conformal Prediction and
  Non-Exchangeable Data." JMLR 25, 2024, pp. 1–38.
- Ding, T., Angelopoulos, A., Bates, S., Jordan, M., Tibshirani, R.J. "Class-Conditional
  Conformal Prediction with Many Classes." NeurIPS 2023, pp. 64555–64576. arXiv:2306.09335.
- Vovk, V., Lindsay, D., Nouretdinov, I., Gammerman, A. "Mondrian Confidence Machine."
  Technical report, Royal Holloway University of London, 2003. Unpublished — retained only
  as the historical origin of group-conditional conformal prediction.
- Prathifkumar, T., Mathews, N.S., Nagappan, M. "Does SWE-Bench-Verified Test Agent Ability
  or Model Memory?" arXiv:2512.10218 (preprint).
- Liu, K., Koyuncu, A., Bissyandé, T.F., Kim, D., Klein, J., Le Traon, Y. "You Cannot Fix What
  You Cannot Find! An Investigation of Fault Localization Bias in Benchmarking Automated
  Program Repair Systems." ICST 2019. arXiv:1812.07283.
- Just, R., Jalali, D., Ernst, M.D. "Defects4J: A Database of Existing Faults to Enable
  Controlled Testing Studies for Java Programs." ISSTA 2014.
- Zhang, Q., Fang, C., Xie, Y., Ma, Y., Sun, W., Yang, Y., Chen, Z. "A Systematic Literature
  Review on Large Language Models for Automated Program Repair." ACM TOSEM (in press).
  arXiv:2405.01466.

### Background, vetted in the 2026-09-17 checkpoint (`docs/decisions.md`), not re-verified this pass

- Zhang, Y., Ruan, H., Fan, Z., Roychoudhury, A. "AutoCodeRover: Autonomous Program
  Improvement." ISSTA 2024. arXiv:2404.05427.
- Xia, C.S., Deng, Y., Dunn, S., Zhang, L. "Agentless: Demystifying LLM-based Software
  Engineering Agents." FSE 2025. arXiv:2407.01489.
- Yang, J., Jimenez, C.E., Wettig, A., Lieret, K., Yao, S., Narasimhan, K., Press, O.
  "SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering." NeurIPS 2024.
  arXiv:2405.15793.
- Wang, X. et al. "OpenHands: An Open Platform for AI Software Developers as Generalist
  Agents." ICLR 2025. arXiv:2407.16741.
- Lyu, M.R., Ray, B., Roychoudhury, A., Tan, S.H., Thongtanunam, P. "Automatic Programming:
  Large Language Models and Beyond." arXiv:2405.02213.
- Kadavath, S. et al. "Language Models (Mostly) Know What They Know." arXiv:2207.05221.
- Kuhn, L., Gal, Y., Farquhar, S. "Semantic Uncertainty: Linguistic Invariances for
  Uncertainty Estimation in Natural Language Generation." ICLR 2023. arXiv:2302.09664.
- Quach, A., Fisch, A., Schuster, T., Yala, A., Sohn, J.H., Jaakkola, T., Barzilay, R.
  "Conformal Language Modeling." ICLR 2024. arXiv:2306.10193.

**Explicitly not used to support any claim in this document**: RisCoSet (arXiv:2605.12201),
"Functional Entropy" (arXiv:2605.28500), and "Code Is More Than Text" (arXiv:2606.09577) are
mentioned only as inherited background framing (already vetted 2026-09-17); RisCoSet's quoted
improvement percentage remains explicitly unconfirmed per the prior checkpoint's own caveat
and is not repeated here as a number.
