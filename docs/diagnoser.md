# Diagnoser

**Status: Phase 4C-L, 2026-09-20 — an `OllamaProvider` adapter is implemented,
offline-verified, and has completed exactly one local development/pilot smoke call.** Phase
4C's `AnthropicProvider` remains implemented and offline-verified but has still made zero real
calls (no API key configured). This document's Anthropic section below is unchanged from
Phase 4C. The Ollama smoke call (see "Ollama adapter" below) is a development/pilot
integration check, not the final research experiment — one call, on one synthetic case, with
one already-locally-installed model. **No diagnosis-accuracy, quality, or calibration claim
follows from it.**

## Responsibility and non-responsibilities

**Responsibility**: given a `DiagnoserInput` built from an existing `CollectorOutput`, produce
one structured `Diagnosis` — a root-cause hypothesis, grounded where possible in cited
files/symbols, plus a self-reported, explicitly-uncalibrated confidence signal. One provider
call, no loop, no retry (`ARCHITECTURE.md`'s "single LLM call in v1").

**Non-responsibilities**: no patch, diff, or repair instruction of any kind; no tool use; no
repository-wide search, RAG, or vector database; no multi-agent framework or debate; no
Validator execution; no Gatekeeper decision; no PR; no GitHub API access; no LLM SDK
dependency in the core module (isolated behind `LLMProvider`, see below).

## Model-visible boundary

`DiagnoserInput` (`src/renacir/diagnoser/models.py`) is an explicit allowlist built by
`renacir.diagnoser.diagnoser.build_diagnoser_input()` from a `CollectorOutput` —
`CollectorOutput` itself is never passed to a provider, and `build_diagnoser_input()`'s
signature takes only a `CollectorOutput` and a condition string, never a `BenchmarkCase`, so
it structurally cannot read `reference_repair`, `independent_checks`, `upstream`, `curation`,
or `test_overlay` even by accident.

Fields: `failing_test`, `command`, `repository_identity` (from `ModelFacingContext`),
`exit_code`, `stdout`, `stderr`, `parsed_failure`, `selected_context`, `repository_structure`,
`runtime`.

**Deliberately excluded, corrected from the Phase 4A proposal**: `category` (benchmark
taxonomy metadata — `"assertion"` | `"import"`). It is not a `DiagnoserInput` field and never
appears in the rendered prompt under any label. It remains available evaluator-side via
`BenchmarkCase.category` for stratified analysis, but a real CI failure would never arrive
pre-labeled with it, and it adds no necessary diagnostic information beyond what
`parsed_failure`/`stdout`/`stderr`/visible source already carry.

**Retrospective-overlay boundary, preserved exactly as Phase 3 left it**: `selected_context`
is copied verbatim from `CollectorOutput`, which already categorically excludes
`case.test_overlay.target_path` regardless of traceback membership. The Diagnoser adds no new
read path into `reference/` or the overlay. For a reconstructed real case, the model may see
the resulting execution evidence (stdout, stderr, exit code, parsed exception/traceback, the
failing node id) — never the overlay's source text. Verified for all 3 real cases in
`tests/diagnoser/test_diagnoser_leakage.py::test_real_case_retrospective_overlay_source_never_appears_in_prompt`,
which builds the actual `CollectorOutput` and actual rendered prompt, not a synthetic stand-in.

**Currently absent, not silently assumed**: "legitimate pre-fix issue/reproduction
information" for real cases. No such field exists anywhere in the pipeline today —
`CollectorOutput` carries only execution evidence, and `UpstreamProvenance.issue_url` is Tier
C/D and never read by Collector. For the 3 current real cases, `DiagnoserInput` in practice
reduces to the reconstructed failure's execution evidence only. Adding issue-text surfacing
would be a Collector change, out of scope here.

## Output schema

```python
class Diagnosis(BaseModel):
    root_cause_summary: str  # max 2000 chars
    suspected_files: list[str] = []  # max 20 items, each max 500 chars
    suspected_symbols: list[str] = []  # max 20 items, each max 200 chars
    reasoning_summary: str  # max 4000 chars
    diagnosis_confidence: float  # 0.0-1.0, enforced
    insufficient_context: bool
```

No patch, diff, replacement-code, or repair-instruction field exists in this schema — checked
structurally by `tests/diagnoser/test_diagnoser_models.py::test_diagnosis_schema_has_no_patch_or_diff_field`,
not left to prompt-following alone. Bounds are enforced by Pydantic validation: an
out-of-range or oversized field raises `ValidationError`, recorded as
`parse_status="validation_error"` in the run record — never silently truncated or accepted.

## Self-reported `diagnosis_confidence` — exact semantics

Per `docs/research_protocol.md` §10.7, this project's *operational* definition of confidence
is `P(tier-1-correct | signal)` — but that is what confidence must mean before it is used, not
a property this number has by construction. `diagnosis_confidence` is:

> The model's own self-assessed belief that `root_cause_summary` correctly identifies the
> actual underlying defect, elicited by explicit prompt instruction, as a number in `[0.0,
> 1.0]`. It is **not** validated as calibrated. It is **not** to be interpreted as `P(correct)`
> until an empirical calibration check is performed (§10.7/§10.8, both open). It is **not**
> used by any decision logic — there is no Gatekeeper. It is recorded for later ablation as one
> candidate Gatekeeper signal (`ARCHITECTURE.md`'s B2 candidate) among several, per
> `docs/research_protocol.md` §9.

This follows directly from Fisch et al. (`docs/literature_review.md` §3, full-read): a
good-looking risk-coverage outcome does not itself prove the underlying confidence *values*
are calibrated.

## Insufficient-context semantics

`insufficient_context: bool` is first-class, not inferred from a low confidence value — a
model can be unsure-but-still-guessing vs. genuinely lacking material to reason from, and
these are different failure modes worth distinguishing. The system prompt explicitly
instructs the model that returning `insufficient_context=true` is valid and preferred over
fabricating a specific cause. **Never set automatically from retrieval diagnostics** — that
decision belongs to the model, based only on what it was actually shown; `RetrievalDiagnostic`
is not visible to the model at all (see "Retrieval-diagnostic independence" below).

`httpie-custom-host-header` (empty `selected_context`, per Phase 3's own measurement, in the
`full_context` condition) is the natural test case for this path, and per the governing
instruction for this phase: if a real experiment run later shows the model fabricating a
specific root cause despite empty context, **that result is data to report, not a bug to
route around**.

## Provider abstraction

```python
class LLMRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    model: str
    temperature: float
    max_tokens: int


class LLMResponse(BaseModel):
    raw_text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_seconds: float | None = None
    provider_error: str | None = None


class LLMProvider(Protocol):
    def generate(self, request: LLMRequest) -> LLMResponse: ...
```

One method, no retry policy, no rate limiting, no multi-provider routing. The Diagnoser core
never sees an API key — a future concrete adapter (e.g. `AnthropicProvider`, **not
implemented in this phase**) would read its own provider-specific secret (e.g.
`ANTHROPIC_API_KEY`) itself, entirely below this interface. `FakeProvider`
(`src/renacir/diagnoser/providers/fake.py`) is the only implementation that exists today —
testing infrastructure, never an experimental baseline, configured at construction time with
canned `LLMResponse`(s), records every `LLMRequest` it receives, makes no network call.

## Prompt versioning and run records

`src/renacir/diagnoser/prompts/v1.py` — `PROMPT_VERSION = "diagnoser-v1"`, a git-tracked
`SYSTEM_PROMPT` constant, and a pure, deterministic `render_user_prompt(DiagnoserInput) ->
str`. Any wording change must bump the version string, per `docs/research_protocol.md` §15's
"prompts frozen/hashed... any change re-declares the fold spent." Delimiter labels
(`execution_stdout`, `execution_stderr`, `source_file`, `repository_structure`) name only
generic evidence categories — never a benchmark/evaluator concept.

`DiagnosisRunRecord` maps §15's logging requirements field-for-field: `case_id`, `condition`,
`run_id` (uuid, distinguishes repeated attempts), `provider`, `model`, `prompt_version`,
`temperature`, `max_tokens`, `timestamp`, `renacir_commit` (git HEAD at run time),
`input_fingerprint` (SHA-256 over the exact rendered system+user prompt — computed by
`fingerprint_request()`, never over a secret, since none exists in this material), the exact
`rendered_system_prompt`/`rendered_user_prompt` sent, `raw_response`, `parsed_diagnosis`,
`parse_status` (`ok` | `parse_error` | `validation_error` | `provider_error`),
`provider_error`, `grounding_violation`, `latency_seconds`, `input_tokens`, `output_tokens`.

`run_id` is the only field distinguishing repeated attempts — **K is not chosen anywhere in
this schema or code**, per `docs/research_protocol.md` §14's explicit deferral.

**No automatic retry, by design**: `diagnose()` calls `provider.generate()` exactly once. A
parse failure, a schema-validation failure, or a provider error is recorded as experimental
data (`parse_status`) and returned — never retried, never repaired with a second model call.

## Grounding

`suspected_files` entries are checked against every path the model was actually shown:
`selected_context` paths, `parsed_failure` traceback frame files, and bare
`repository_structure` filenames (seen as a name, even without content). A citation outside
that set is a `grounding_violation` — recorded, never silently dropped, and the original
`parsed_diagnosis` is never deleted or altered because of it.

**`suspected_symbols` grounding is deliberately not implemented.** Reliably verifying that a
free-text symbol name genuinely appears in visible source would require either real parsing
(AST-level, per-construct) or a naive substring search prone to false positives/negatives
(e.g. a name appearing in a comment, or as a common English word) — exactly the "invented
brittle validator" this phase was told not to build. This is recorded as a limitation, not
silently patched over with an unreliable check.

## Two input conditions (infrastructure only — not yet an experiment)

- **`failure_output_only`**: `selected_context` and `repository_structure` forced to `[]`;
  everything else (failing test id, command, exit code, stdout/stderr, parsed failure,
  runtime) unchanged.
- **`full_context`**: `selected_context`/`repository_structure` populated exactly as
  `CollectorOutput` produced them.

Same prompt structure, output schema, and provider configuration otherwise. This exists to
later isolate whether Collector's selected source context adds measurable value over failure
text alone — no experiment comparing them has been run.

## Diagnosis evaluation plan

`src/renacir/evaluation/diagnosis.py` — evaluator-only, computed strictly after a
`DiagnosisRunRecord` already exists; nothing in `renacir.diagnoser` imports it. Reuses
`renacir.evaluation.retrieval.reference_relevant_files()` for "what did the historical repair
touch" rather than defining a second reference set.

**Automated now**: suspected-file precision/recall/F1 against `reference_relevant_files`;
grounding-violation rate; parse/validation success rate; insufficient-context rate;
latency/token summaries. All return `None` (never a fabricated `0`/`False`) when not
computable for a given record.

**Requires human/blinded annotation, not automated, not faked as automation**: whether
`root_cause_summary` is *semantically* correct. File-overlap can't tell you the model pointed
at the right file for the right reason — a proposed 4-point blinded rubric (read `root_cause_
summary`/`reasoning_summary` before consulting the reference repair):

1. Correctly identifies the actual root cause and mechanism.
2. Identifies the correct general area/file but not the precise mechanism.
3. Plausible-sounding but factually wrong or unrelated to the actual bug.
4. Non-answer / fabricated / incoherent.

This rubric is **documented, not implemented** — no scoring code exists for it, and none of
this phase's tests invoke it. Applying it is a deliberate, separate, later step, consistent
with `docs/research_protocol.md` §17's already-logged single-author-bias threat.

**Final diagnosis-accuracy metric remains unresolved**, exactly as `docs/research_protocol.md`
§10.11 already states — the automated file-overlap proxy here is the same provisional
candidate that section already anticipated, not a new decision.

## Retrieval-diagnostic independence

`RetrievalDiagnostic` (Phase 3 audit) is never visible to the model and never influences
`DiagnoserInput` construction — `build_diagnoser_input()` doesn't take one as a parameter at
all. Proven, not just asserted, by
`tests/diagnoser/test_diagnoser_leakage.py::test_retrieval_diagnostic_computation_cannot_alter_diagnoser_input`,
which computes a `RetrievalDiagnostic` (reading `case.upstream`/`case.reference_repair`)
between two `build_diagnoser_input()` calls on the same `CollectorOutput` and confirms both
calls produce an identical result.

## Prompt-injection limitation

Untrusted content (stdout, stderr, each selected file's content, repository structure
entries) is wrapped in `<DATA kind="...">...</DATA>` markers, and the system prompt instructs
the model to treat everything inside them as data, never as instructions, even if it appears
to contain directives. **This is a stated mitigation, not a guarantee.** Two limits, recorded
directly:

1. The delimiting is a soft, textual convention interpreted by the model — not a real parser
   boundary. Source content containing a literal `</DATA>` sequence could locally appear to
   "close" a block early to a naive re-reading; nothing here re-parses or escapes such content.
2. No real model has been tested against this prompt. `tests/diagnoser/test_prompt.py::test_prompt_injection_content_remains_delimited_as_data_not_instructions`
   verifies only that the *rendering* correctly places injected-looking text inside its
   delimited block, structurally unchanged — it says nothing about whether an actual LLM would
   resist following embedded instructions. That is untested and unclaimed.

## Anthropic adapter (Phase 4C)

`src/renacir/diagnoser/providers/anthropic.py` — the smallest adapter satisfying
`LLMProvider`: one `LLMRequest` → one `client.messages.create()` call → one `LLMResponse`. No
retry, no streaming, no tool use, no prompt caching, no batch API, no routing/fallback. Two
implementation details worth recording:

- **The Anthropic SDK defaults to `max_retries=2` internally** — silent transport-level
  retries on transient errors, invisible to this module's own single call site. Explicitly
  overridden to `max_retries=0` when `AnthropicProvider` constructs its own client, so "exactly
  one call" holds at the HTTP level, not just in `renacir.diagnoser.diagnoser`'s own code.
  Verified by `tests/diagnoser/test_anthropic_provider.py::test_real_client_construction_disables_sdk_internal_retries`.
- Only `anthropic.APIError` (covers `AuthenticationError`, `RateLimitError`,
  `APIConnectionError`, and other SDK-defined failures) is mapped to `LLMResponse.provider_error`.
  Any other exception (e.g. a bug in this adapter's own request construction) propagates
  rather than being misreported as a provider-side failure.

**Secrets**: `AnthropicProvider.__init__(api_key: str, client=None)` takes the key as a plain
argument — it never reads `os.environ` itself, which keeps it fully unit-testable without
touching real configuration. The CLI (`python -m renacir diagnose`) resolves the key from
`renacir.config.Settings.anthropic_api_key` (itself sourced from the `ANTHROPIC_API_KEY`
environment variable or `.env`, via the project's existing `pydantic-settings` pattern) —
never from a CLI argument, never printed, never stored in `DiagnosisRunRecord` (the schema has
no field for it), never included in the rendered prompt or its fingerprint. Verified end-to-
end by `tests/diagnoser/test_anthropic_provider.py::test_api_key_never_appears_in_a_full_diagnose_run_record`
and by CLI-level tests confirming a deliberately-planted fake secret never appears in stdout/
stderr even on the refusal paths.

**Model identifier**: never defaulted anywhere in code. `python -m renacir diagnose` requires
`--model` or the `LLM_MODEL` environment variable; if neither is set, the CLI refuses before
touching the provider or the API key at all. `DiagnosisRunRecord.model` always records the
exact string actually requested.

**CLI safety gate**: `python -m renacir diagnose <case-id> --condition {failure_output_only,full_context}
--provider anthropic [--model <id>] [--temperature 0.0] [--max-tokens 1024] --allow-api-call`.
Without `--allow-api-call`, the command refuses immediately — before resolving the API key,
before constructing a provider, before touching the network — printing a refusal message and
exiting non-zero. This is a cost/safety guard, not an experimental variable; it is not meant
to be toggled as part of comparing conditions.

**Persistence**: `save_run_record()` writes one `DiagnosisRunRecord` as JSON to a local,
git-ignored directory (`artifacts/diagnosis_runs/` by default, added to `.gitignore` this
phase). No database. A saved run record is raw experimental output, not methodological ground
truth — it is never read back into any test or into the frozen benchmark.

## Ollama adapter (Phase 4C-L)

`src/renacir/diagnoser/providers/ollama.py` — a second `LLMProvider` implementation, for local
inference via [Ollama](https://ollama.com)'s REST API, added alongside (not instead of)
`AnthropicProvider`. Same architecture: `Diagnoser → LLMProvider → OllamaProvider →
<model tag>`.

**Model-family-agnostic by construction, not just by intent**: the exact model tag (e.g.
`qwen2.5-coder:7b`) flows through `LLMRequest.model` exactly like any other provider.
`OllamaProvider` and `renacir.diagnoser.diagnoser` contain no model-family-specific branch,
string match, or default anywhere — verified by
`tests/diagnoser/test_ollama_provider.py::test_generate_is_model_family_agnostic` and
`::test_fetch_model_metadata_is_model_family_agnostic`, both of which swap in an unrelated
model family (`llama3.1:8b`) and confirm identical code paths handle it. Using a different
locally-pulled model requires no code change in this module or in the Diagnoser core.

**Transport**: Python standard library `urllib` only — no SDK, no new dependency. POSTs to
`/api/chat` (`messages: [{role: system}, {role: user}]`, matching `LLMRequest` exactly) and
reads `/api/tags` for reproducibility metadata (see below). No retry, no streaming, no tool
use. Ollama reports some failures (e.g. an unpulled model) as a 200 response with an `"error"`
key rather than an HTTP error status — mapped to `provider_error` the same way as a transport
failure, tested explicitly
(`tests/diagnoser/test_ollama_provider.py::test_generate_maps_ollama_error_payload_to_provider_error`).

**Never downloads a model.** `OllamaProvider` only ever calls a model already present
locally; if it isn't, the call fails and is reported as a `provider_error` like any other
failure — there is no pull/fetch logic anywhere in this module.

**Reproducibility metadata**: `fetch_model_metadata(model)` — deliberately separate from
`OllamaProvider.generate()`, never part of `LLMRequest`/`LLMResponse`, never called by the
Diagnoser core — queries `/api/tags` and extracts generically-named fields Ollama already
reports (`details.family`, `.quantization_level`, `.parameter_size`, `.context_length`, plus
the model's content digest) into `DiagnosisRunRecord.model_metadata` (new, generic,
provider-agnostic field: `dict[str, str]`, empty for providers with nothing extra to record,
such as Anthropic). No model-family-specific key lookup exists anywhere in this function —
confirmed by testing it against both `qwen2.5-coder:7b` and a fabricated `llama3.1:8b` entry
with identical extraction logic.

**CLI**: `python -m renacir diagnose <case-id> --condition {...} --provider ollama --model
<tag> --allow-api-call [--temperature 0.0] [--max-tokens 1024]`. Same `--allow-api-call` gate
as Anthropic — local and free is not treated as license for silent/automatic invocation. No
`ANTHROPIC_API_KEY` (or any secret) is required or read on this path; verified by
`tests/test_diagnose_cli.py::test_ollama_provider_requires_no_api_key`.

**Development/pilot smoke call performed (2026-09-20)**: `assertion-average-off-by-one` /
`full_context`, model `qwen2.5-coder:7b` (already locally installed — no model was
downloaded), temperature 0.0, max_tokens 1024. Recorded model metadata: digest
`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`, family `qwen2`,
quantization `Q4_K_M`, parameter_size `7.6B`, context_length `32768`. Result:
`parse_status: ok`, `grounding_violation: false`, `insufficient_context: false`,
`diagnosis_confidence: 0.95`; the model correctly identified `stats.py`'s off-by-one
denominator as the root cause. **This is one development/pilot integration call, not the
final research experiment** — it demonstrates the Ollama path works end-to-end and produces a
well-formed, grounded `Diagnosis`; it is not a claim about `qwen2.5-coder:7b`'s general
diagnostic accuracy, and `diagnoser-v1` was not modified based on this single result, per the
prompt-freeze rule already established for the Anthropic path. The full run record is saved
under `artifacts/diagnosis_runs/` (git-ignored, not committed, not read back into any test or
the benchmark).

## What has and has not happened

Implemented and tested offline (Phase 4B): `DiagnoserInput`, `Diagnosis`, `DiagnosisRunRecord`
schemas; the versioned prompt renderer; the `LLMProvider` protocol and `FakeProvider`; strict
parsing/validation with no retry; grounding-violation detection; the two input conditions; the
automated evaluation helpers. Implemented and tested offline (Phase 4C): the `AnthropicProvider`
adapter (mocked at the SDK boundary in every test) and the `diagnose` CLI command with its
`--allow-api-call` gate — **zero real Anthropic calls have been made** (no API key configured
in this environment). Implemented, tested offline, and exercised with exactly one real local
call (Phase 4C-L): the `OllamaProvider` adapter and `fetch_model_metadata()`. **Not done, not
claimed**: no real Anthropic network call of any kind; no diagnosis-accuracy, quality, or
calibration claim of any kind, for either provider — the one Ollama smoke call is a
development/pilot integration check on a single synthetic case, not evidence about model
quality in general.
