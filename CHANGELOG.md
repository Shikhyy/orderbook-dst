# CHANGELOG

## [Unreleased]

### Added
- Clarification `R-A6 [Declared]`: Basket rollback 0-based leg indexing in R-A4 (decision OQ-01).
- Clarification `R-A7 [Declared]`: Basket IOC leg success check runs before remainder cancel in R-A3 and R-B5 (decision OQ-02).
- Clarification `R-W7 [Declared]`: Account iteration order in R-W1 and R-W6 is lexicographic string order (decision OQ-03).
- Clarification `R-M5 [Declared]`: Explicit lock release to free_cash on complete order fill in R-M4 (decision OQ-04).
- Clarification `R-P5 [Declared]`: Raw best opposite price checked in R-P2 without filtering same-account orders (decision OQ-05).
- Clarification `R-X1 [Declared]`: Environment execution convention applying skill intent when skills are missing (decision OQ-06).
- Clarification `R-X2 [Declared]`: Missing policy files scaffolding during initial setup (decision OQ-07).
- Clarification `R-F4 [Declared]`: Inclusive boundary condition for T0 tier threshold in R-F2 (decision OQ-08).
- Milestone M8-prep evaluation runner and human audit tools:
  - Evaluation runner `tools/run_all.sh`: Verifies preflight checks, runs dry-run cost estimation, supports pilot and main evaluation runs with confirmation prompts.
  - Human audit tool `tools/human_audit.py`: Selects 20 stored trials with fixed seed (10 pass, 10 fail), blinds grader outcomes, computes 2x2 agreement matrix and Cohen's Kappa, and formats audit report in `results/human_audit.md`.
  - Unit tests in `tests/test_human_audit.py` verifying sampling and agreement metrics against hand-calculated values.
  - Added `make audit` target to Makefile and allowed `tools/*.sh` in `publish_allowlist.txt`.
  - Added AI-drafted difficulty reasons across all 8 tasks in `tasks/*/task.toml` and `EXPERT_REVIEW.md` with `author_signoff = false` pending author rewrite.

### Corrected (2026-11-04, second pilot)
- **False-pass gap in the hidden simulation.** `nemotron-3-nano` never stored the new mark price in `state.mark_price` (R-W1) and failed the visible `test_no_breach`, yet scored T3 = 1.00: the end-of-trace comparison covered balances and positions only. Tier 3 now also requires the whole final state (`state_hash`) to equal the reference's, for every task. The reference, `reference_alt` and the clean-room `reference_alt_v2` all still score 1.0 on all 8 tasks, and all 36 mutants still fail. New mutant `f4_waterfall_b/m_mark_price_not_stored` reproduces the model's bug and fails all 20 seeds. Recorded as `HYPOTHESES.md` amendment A2.
- **Groq's free tier cannot run this benchmark.** Its 8,000 tokens-per-minute cap applies per request and the prompts are 5.7k to 9.3k tokens as providers count them (HTTP 413 on `gpt-oss-120b` and `qwen3.8-27b`). A per-minute 429 was also misread as a daily quota because the error text contained a "billing" link; per-minute limits are now waited out using the provider's "try again in Ns", and a 413 skips that task (listed as skipped, not as a model failure) instead of stopping the model.
- Reasoning models that spend the whole token budget thinking return no answer. Such trials are labelled `OUTPUT_TRUNCATED` (not `FORMAT_ERROR`), are not retried with the same budget, and the report tells you to raise `max_tokens`.

### Added (2026-11-04, visible progress)
- Long runs looked hung: rate-limit waits (Mistral's free tier is about 1 request/minute) printed nothing. `harness/progress.py` now prints a counter with ETA per trial (`[12/40] [ETA ~25m] model | task | trial 1/5: calling model`), announces rate-limit waits and retries, and writes a heartbeat to `results/<run>/progress.json`. `make status` (one snapshot) and `make watch` (live) read it: running or stopped, bar, ETA, the call in flight and how long it has waited, per-model done/passed/mean score, models stopped early.
- Empty provider replies (observed: Mistral Large ending a turn with `finish_reason=tool_calls` and no text, although no tool was offered) are retried up to twice and the count is stored as `empty_reply_retries` in the trial record, so a provider quirk is not scored as a wrong answer.
- Rate limiter looks up `time.sleep` at call time, so tests do not really sleep.

### Corrected (2026-11-04, found by the first real-model run)
- **The output-format instructions contradicted each other, and the extractor accepted only one of them.** The system message puts `### FILE: <path>` above the code fence; the `f1_fee_a`, `f1_fee_b`, `f3_fix_a` and `f3_fix_b` instructions showed it as the first line *inside* the fence; the extractor accepted only the first layout. `nemotron-3-ultra` followed an instruction exactly and was scored `FORMAT_ERROR` on two tasks; regrading its saved replies gives 1.00 on both. Fixes: the extractor accepts both layouts (`find_file_blocks`); all instructions that show a layout now show the system message's layout, and `f2_replace_a` and `f2_replace_b` gained the same example; `--regrade` now re-extracts from the saved `reply.txt`, so an extractor fix applies to replies already paid for. `tests/test_output_format_consistency.py` fails if an instruction contradicts the system message and checks that both layouts extract all 8 reference solutions.
- **The Docker sandbox test had been skipped, which hid a flaky first run.** With Docker running it failed once because the 10 s sandbox call included pulling `python:3.11-slim`. The test now pulls the image first. `make grade-docker` and the image build (`docker build`, then `make validate` and all tests inside the container) pass. `results/pilot/` is excluded from the image.
- **Coupled task instructions did not document the `engine` object.** The first real model (`gemini-3.5-flash`) failed `f1_fee_b` and `f2_replace_b` with `'Engine' object has no attribute 'config'`: the interface said `engine: "Engine"` but never said the config is `engine.cfg` and the state is `engine.state` (the prompt shows `state.py` and `config.py`, not `engine.py`). That is a missing specification, not a model limitation, and it would have failed every model on those tasks. Each coupled instruction now has an "engine argument" section listing exactly the members its reference solutions use (`cfg`, `state`, `dispatch`, and the `process` alias). The partial pilot from before the fix was discarded.
- `tests/test_instruction_completeness.py` fails if a reference solution (`reference/` or the clean-room `reference_alt_v2/`) uses an `engine.<member>` the instruction does not document. It immediately caught one more gap: the clean-room author, working from the instruction alone, had used the `engine.process` alias.

### Added (2026-11-04, Modal with a spending cap)
- Per-model `budget_usd` and `usd_per_second`: each call is charged `latency_s * usd_per_second` and the run stops before a call that could exceed the budget; spend already recorded in `trials.jsonl` counts, so the cap holds across resumes. Also a per-model `tasks = [...]` subset and `--only label1,label2`.
- `models.modal.toml` (git-ignored, not used by `make run`) configures the Modal-hosted DeepSeek endpoint with `allow_paid = true` and a $0.40 cap on a $1 credit.

### Added (2026-11-04, verified free providers)
- `api_key_secret_env` for hosts that want a two-part bearer token (Modal proxy auth, `<id>.<secret>`). A Modal endpoint answered a live test, but Modal bills GPU time, so the free-only guard refuses it unless `allow_paid = true`; the entry is in `models.free.example.toml` commented out.
- OpenCode Zen (`opencode.ai/zen/v1`) was tested and is not used: its free models return 429 "Free usage limit reached" outside the OpenCode app, and every other model on that key is paid.
- `harness/freeguard.py`: every run mode refuses a model unless its host is a known free-tier host (Google AI Studio, Groq, Mistral Experiment, NVIDIA NIM, Cerebras) or it is an OpenRouter `:free` model. Paid adapters, GPU hosts that bill compute and unknown endpoints need an explicit `allow_paid = true`. It cannot see account billing; keep billing off in each provider dashboard.
- `content_to_text`: Mistral's reasoning models return message content as a list of blocks (`thinking`, then `text`). The OpenAI-compatible adapters now keep only the text blocks; before, every such reply would have broken file extraction.
- Live check on 2026-11-04: Gemini (`gemini-3.5-flash`, `3.1-flash-lite`), Groq (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`), Mistral (`mistral-large-4`, `ministral-8b-latest`) and OpenRouter (`nvidia/nemotron-3-ultra-550b-a55b:free`, `nvidia/nemotron-3.5-super-vl:free`) answered; five of them ran one `f1_fee_a` trial end to end through the harness. Not usable on this account: `gemini-2.5-pro`/`2.5-flash` (404), `gemini-pro-latest` (429), `thinkingmachines/inkling:free` (agent harnesses only).

### Added (2026-11-04, free-tier runs)
- `models.free.example.toml`: hosted free-tier presets: Google AI Studio Gemini (OpenAI-compatible endpoint), NVIDIA NIM, Groq (mid and small models), plus optional Mistral, OpenRouter `:free` and Cerebras. Each model names its key variable with `api_key_env`; `.env.example` lists them.
- `harness/ratelimit.py`: every adapter is wrapped with per-model `rpm` spacing, an `rpd` cap per run, and bounded exponential-backoff retries on 429/5xx/timeouts (honouring Retry-After). On a daily quota, an auth error or exhausted retries, that model stops cleanly with no record written, the other models continue, and re-running the same command resumes. SDK-level retries are disabled so this is the only retry layer.
- `tools/list_models.py` (`make list-models`): lists the model IDs each configured key can use and checks every `model_id` in `models.toml` (read-only `/models` calls).
- `make pilot` (1 trial per task) and `MODELS`, `TASKS`, `TRIALS` overrides for `run`, `dry-run` and `feedback`.
- Prompt-truncation check: a trial is flagged when the provider reports far fewer input tokens than the prompt contains (for example a provider or server with a 4096-token context would cut every prompt here). The report warns about flagged trials.
- Report sanity checks from the guide: 0% everywhere, no headroom, a smaller `tier` outscoring a larger one, tasks that no model fails or every model fails badly, high format-error rates, incomplete runs.
- Transcripts include a unified diff of the model's file against the reference solution.

### Added (2026-11-04, research tooling)
- `tools/mutant_tier_analysis.py` (`make mutant-tiers`): grades all 35 mutants and records which tier catches each. Result in `results/grader_analysis/`: 32 fail a visible test, 2 are caught first by checkpoints, 1 (`f2_replace_b/m_lock_uses_current_rate`) only by the hidden simulation.
- `tools/make_demo.py` (`make demo`; the target existed but the script did not): grades the reference and that mutant side by side.
- `tools/export_transcripts.py` (`make transcripts`): exports, per model and task, the lowest-scoring failure, any near miss and one pass from a real run, with the verbatim reply and grader diagnostics.
- Grader `seed_failures`: every failing hidden seed records all labels seen at its first failing event (D1 plus any invariant broken at that event). Diagnostic only; scores and the feedback-loop prompt are unchanged.
- `harness/report.py` now writes the guide's results table (exact model ID and settings, pass rate with CI, pass@k, pass^k, cost), a per-task table, per-trial outcome types, near misses, and the computed H1–H5 metrics, plus H3 from feedback-loop runs.
- `models.ablation.example.toml` and `[model.settings.extra]` pass-through for reasoning-effort ablations.
- `HYPOTHESES.md` amendment A1, written before any real model run, fixing how each hypothesis is computed.
- Makefile targets `dry-run`, `feedback`, `report`, `transcripts`, `mutant-tiers`.

### Corrected
- H2 statistics: the old test paired trial *i* of task A with trial *i* of task B and applied McNemar. Those are independent calls on different tasks, so the pairing was invalid. It is replaced by a one-sided stratified permutation test per family; McNemar is now used only for H3, where trials really are paired. The report no longer pools trials from different models in one comparison.
- Reference solutions did not pass the grader models face: 23 Variant B references and mutants imported `exchange_core.rules.*`, which the task instructions forbid and the candidate grader rejects with `FORBIDDEN_IMPORT` (score 0). V1–V3 graded them in a mode that skips that check. The rule logic is now written out in those files, copied from the engine's own rule module, which is exactly what the import resolved to, so all 59 reference and mutant scores are unchanged. V1–V3, `make mutant-tiers` and `make demo` now grade in candidate mode, and `tests/test_reference_import_policy.py` keeps it that way.
- Grader validation V2 checked only `reference_alt/`, which is not clean-room independent; it now also checks the clean-room `reference_alt_v2/` (all 8 tasks pass).
- Reproducibility: `requirements.txt` pinned to tested versions (verified on Python 3.12 and 3.14). The Dockerfile ran `make`, which `python:3.12-slim` does not include, and copied the host `.venv`; it now calls Python directly and has a `.dockerignore`.
- README rewritten: claims are limited to what `make validate`, `make test` and `make mutant-tiers` show; the "unit tests fail to catch these bugs" claim is replaced by the measured mutant-tier result; real-world incidents are worded more carefully; threats to validity, cost and runtime added.
- Simulated results removed: `results/` and `transcripts/` from commits `710420a`, `f733c6c` and `038bd25` were not model output. `scratch/generate_benchmark_results.py` built each "trial" from the reference, alt reference or a mutant on a hand-written schedule, with random latency and token counts. `scratch/run_feedback_trials.py` did the same for the feedback loop (mutant as turn 0, alt reference as turn 1). All of those files and every number taken from them in `README.md`, `HYPOTHESES.md` section 3, `SUBMISSION_DESCRIPTION.md` and `VIDEO_SCRIPT.md` Parts 3–4 were removed. `AI_USE.md` now records this. Results will only come from real API runs through `harness/run_eval.py`.
- Harness adapters: `temperature` is now sent only when `models.toml` sets it (it was silently defaulting to 1.0 while the README claimed T=0). The Anthropic adapter joins every text block instead of reading only the first. The OpenAI adapter now passes `max_tokens` as `max_completion_tokens` and supports `reasoning_effort`. The OpenAI-compatible adapter now receives the top-level `base_url` from `models.toml` and reads its own `OPENAI_COMPAT_API_KEY`.
- Cost estimates come from per-model `price_in_per_mtok` / `price_out_per_mtok` in `models.toml` instead of a stale hard-coded price table. Every trial record now stores the settings sent, the model ID the provider reported serving, and the stop reason. `run_meta.json` records the model configuration and task list.
- Mutant count and mutation testing disclosure: Clarified that the benchmark contains exactly 35 hand-crafted mutants across the 8 tasks (not 42). Formal mutation testing (mutmut) has not been run yet. Noted that `reference_alt/` was not clean-room independent; clean-room isolation was implemented in `reference_alt_v2/`.
- Checkpoint provenance disclosure: Corrected historical descriptions characterizing Tier 2 trace checkpoints as "hand-calculated" in prior milestones. All 51 checkpoints across all 8 tasks are designated with `source: engine` because their values were generated via reference engine execution. Hand calculations are documented separately in audit worksheets.
- Audit worksheet methodology: Noted that current Tier 2 audit worksheets in scratch/ re-derive some checkpoint transitions starting from engine-provided pre-states rather than computing the entire trace strictly end-to-end from event 0 by hand; full independent blind verification from scratch without engine pre-states is currently pending. Also clarified that the total count of checkpoints across all 8 tasks is 59 (not 51), all of which carry `source: engine`.

## [M7] 2026-11-02

### Added
- Tasks `f4_waterfall_b` (Family F4, Liquidation waterfall and margin shock) and `f5_basket_b` (Family F5, Multi-leg basket all-or-nothing execution):
  - `tasks/f4_waterfall_b`: `task.toml`, `instruction.md`, 9 public tests in `public_tests/`, and 35-event Tier 2 trace with 8 checkpoints in `tier2_trace.json`.
  - `tasks/f5_basket_b`: `task.toml`, `instruction.md`, 9 public tests in `public_tests/`, and 35-event Tier 2 trace with 8 checkpoints in `tier2_trace.json`.
  - Reference solutions in `reference/f4_waterfall_b/shock.py` and `reference/f5_basket_b/basket.py`.
  - Mutants in `mutants/f4_waterfall_b/` (`m_liq_account_not_updated`, `m_liquidate_first`, `m_locks_not_released_to_cash`, `m_no_recheck_after_cancel`, `m_wrong_account_order`) with `expect.toml`.
  - Mutants in `mutants/f5_basket_b/` (`m_forgot_counter_restore`, `m_forgot_volume_restore`, `m_partial_commit`, `m_reports_not_discarded`, `m_restore_book_only`) with `expect.toml`.
  - Alternative reference solutions in `reference_alt/f4_waterfall_b/shock.py` and `reference_alt/f5_basket_b/basket.py`.
- Statistics and analysis module `harness/stats.py`:
  - `compute_pass_at_k`: unbiased estimator for pass@k given n samples and c correct.
  - `compute_pass_pow_k`: pass^k reliability estimator (c/n)^k.
  - `compute_mttif`: mean trials to first invariant failure.
  - `bootstrap_ci`: hierarchical cluster bootstrap (resampling tasks then seeds) for 95% confidence intervals with 10,000 resamples.
  - `mcnemar_exact_pvalue`: two-sided exact McNemar test for paired binary comparison.
  - `paired_comparison_a_vs_b`: pairwise statistical comparison report.
- Report generation CLI `harness/report.py`:
  - Generates Markdown tables and summary JSON from evaluation run results.
  - Formats pass@k, pass^k, and invariant failure rates across tasks and models.
- Unit test suite `tests/test_stats.py`:
  - 7 unit tests verifying hand-calculated pass@k, pass^k, McNemar exact p-values, bootstrap repeatability, MTTIF, and report generation pipeline (135 total tests passing).
- Gate G3: `make validate` passes all checks V1 to V8 across all 8 tasks (`f1_fee_a`, `f1_fee_b`, `f2_replace_a`, `f2_replace_b`, `f3_fix_a`, `f3_fix_b`, `f4_waterfall_b`, `f5_basket_b`).
- Scope freeze in effect: no additional tasks, rules, or families to be added.

## [M6] 2026-11-02

### Added
- Tasks `f1_fee_a` and `f1_fee_b` (Family F1, Volume-tiered fee and rebate):
  - `tasks/f1_fee_a`: `task.toml`, `instruction.md`, 8 public tests, 40-event Tier 2 trace with 6 checkpoints.
  - `tasks/f1_fee_b`: `task.toml`, `instruction.md`, 9 public tests, 40-event Tier 2 trace with 6 checkpoints.
  - Reference solutions in `reference/f1_fee_a/fee_rule.py` and `reference/f1_fee_b/settle.py`.
  - Mutants in `mutants/f1_fee_a/` (`m_float_math`, `m_off_by_one_boundary`, `m_round_half_up`, `m_whole_fill_new_rate`) with `expect.toml`.
  - Mutants in `mutants/f1_fee_b/` (`m_rebate_not_paid_from_vault`, `m_vault_not_updated`, `m_volume_before_fee`, `m_whole_fill_new_rate`) with `expect.toml`.
- Tasks `f3_fix_a` and `f3_fix_b` (Family F3, FIX session sequencing and replay):
  - `tasks/f3_fix_a`: `task.toml`, `instruction.md`, 9 public tests, 35-event Tier 2 trace with 8 checkpoints.
  - `tasks/f3_fix_b`: `task.toml`, `instruction.md`, 9 public tests, 35-event Tier 2 trace with 8 checkpoints.
  - Reference solutions in `reference/f3_fix_a/session_rule.py` and `reference/f3_fix_b/fix.py`.
  - Mutants in `mutants/f3_fix_a/` (`m_buffer_overwrite`, `m_no_drain`, `m_process_out_of_order`, `m_skip_possdup`) with `expect.toml`.
  - Mutants in `mutants/f3_fix_b/` (`m_double_dispatch_on_drain`, `m_process_out_of_order`, `m_reset_keeps_buffer`, `m_skip_possdup`) with `expect.toml`.
- Second independent implementation in `reference_alt/`:
  - Clean-room implementation authored in isolated worktree with reference solutions removed.
  - All rules in `reference_alt/rules/` (`fee_rule.py`, `replace_rule.py`, `session_rule.py`, `waterfall_rule.py`).
  - All handlers in `reference_alt/handlers/` (`new_limit.py`, `cancel.py`, `replace.py`, `margin_rate.py`, `shock.py`, `fix.py`, `basket.py`, `settle.py`).
  - Task-specific implementations in `reference_alt/` for all 6 tasks (`f1_fee_a`, `f1_fee_b`, `f2_replace_a`, `f2_replace_b`, `f3_fix_a`, `f3_fix_b`).
  - Check V2 (Alt Reference Check) verified and passing with score 1.00 across all 6 tasks.
- Differential test suite:
  - `tests/test_differential.py` verifying exact report stream and state hash equivalence between reference and alternative implementations across all 5 trace profiles.
- Gate: `make validate` passes all checks V1 to V8 across all 6 tasks (`f1_fee_a`, `f1_fee_b`, `f2_replace_a`, `f2_replace_b`, `f3_fix_a`, `f3_fix_b`).


## [M5] 2026-11-01

### Added
- `harness/prompt.py` prompt builder constructing fixed system message, task instruction, target stubs, read-only context files, and SHA-256 prompt hash.
- `harness/extract.py` code extraction parser handling `### FILE: <path>` code blocks, checking expected files, and detecting `MISSING_FILE` and `FORMAT_ERROR`.
- `harness/adapters/` multi-provider model adapters adhering to the <= 30-line constraint:
  - `base.py`: `ModelReply` dataclass and `ModelAdapter` protocol.
  - `anthropic.py`: Anthropic Claude API adapter.
  - `openai.py`: OpenAI API adapter.
  - `openai_compat.py`: OpenAI-compatible API adapter for local/hosted models.
  - `mock.py`: Offline mock adapter for testing and dry runs.
- `harness/run_eval.py` evaluation harness CLI:
  - Supports `--models`, `--mode single_turn`, `--trials`, `--out`, `--tasks`, `--dry-run`, and `--regrade`.
  - Resume capability skipping already-evaluated trials.
  - Generates `run_meta.json`, `trials.jsonl`, and per-trial raw prompt, reply, files, and `score.json`.
- `tests/test_harness_extract.py` test suite covering prompt generation, valid extraction, format error handling, missing file detection, and mock generation.
- Gate G2: `make test` passes (103 passed in 0.20s).

## [M4] 2026-11-01

### Added
- `graders/hidden_seeds.py` with base seed definitions for hidden Tier 3 evaluation (20 seeds per task).
- `graders/sandbox.py` with isolated filesystem overlay and subprocess execution (`run_sandboxed`).
- `graders/dst_grader.py` three-tier deterministic grader (T1 public tests, T2 targeted checkpoints, T3 hidden seeds with D1 and I1-I4 checks).
- `tasks/f2_replace_a`: `task.toml`, `instruction.md`, 9 public tests in `public_tests/`, and 35-event Tier 2 trace with 8 hand-calculated checkpoints in `tier2_trace.json`.
- `tasks/f2_replace_b`: `task.toml`, `instruction.md`, 10 public tests in `public_tests/`, and 35-event Tier 2 trace with 8 hand-calculated checkpoints in `tier2_trace.json`.
- Reference solutions in `reference/f2_replace_a/replace_rule.py` and `reference/f2_replace_b/replace.py`.
- Mutants in `mutants/` with `expect.toml`:
  - `f2_replace_a`: `m_reset_on_decrease`, `m_compare_with_leaves`, `m_keep_on_price_change`, `m_allow_equal_cum`.
  - `f2_replace_b`: `m_lock_uses_current_rate`, `m_lock_not_adjusted`, `m_prio_not_updated_in_state`, `m_counter_not_incremented`, `m_state_changed_on_reject`.
- `tools/make_workspace.py` workspace generator with stubs and test runners.
- `tools/validate_graders.py` validation suite implementing checks V1 through V8.
- Gate G1: `make validate` passes all checks across both tasks.
- `exchange_core/` code lines: 1,489 lines (ENG-10 <= 1500 lines satisfied).

## [M3] 2026-11-01

### Added
- `graders/detrng.py` with 64-bit deterministic RNG implementing xorshift64*.
- `graders/trace_gen.py` supporting five task profiles (`fee_heavy`, `replace_heavy`, `fix_noisy`, `shock_heavy`, `basket_heavy`), ~3% invalid events, and trigger coverage calculation.
- `make_noisy_fix_trace` helper for I4 replay property verification.
- Unit and property tests in `tests/test_detrng.py`, `tests/test_trace_gen.py`, and `tests/test_property_m3.py` (94 tests total).
- Property tests verify I1, I2, I3 on generated traces, I4 replay law, and basket rollback law.
- Gate: `make test` passes.

## [M2] 2026-11-01

### Added
- `exchange_core/book.py` with order book priority and queue primitives.
- `exchange_core/ledger.py` with cash, lock, position, and fee ledger primitives.
- `exchange_core/invariants.py` with Violation dataclass and checks for I1, I2, I3.
- `exchange_core/rules/` pure functions: `fee_rule.py`, `replace_rule.py`, `session_rule.py`, `waterfall_rule.py`.
- `exchange_core/handlers/` stateful handlers: `new_limit.py`, `cancel.py`, `replace.py`, `margin_rate.py`, `shock.py`, `fix.py`, `basket.py`, `settle.py`.
- `exchange_core/engine.py` Engine class with `dispatch`, `process`, and `state_hash`.
- Unit tests for all rulebook worked examples, STP, FIX, basket rollback, invariant sensitivity, and pure rules (69 tests total).
- Engine codebase line count under 1,500 lines (Rule ENG-10: 1,498 lines).
- Gate: `make test` passes.

## [M1] 2026-11-01

### Added
- `exchange_core/intmath.py` with `round_half_even` (R-U2) and `ceil_div` (R-U3).
- `exchange_core/config.py` with `EngineConfig` constants.
- `exchange_core/types.py` with `Order`, `Event`, `Report`, `Fill`, `ReplaceDecision`, `SessionOutcome`, `AccountView`, `WaterfallPlan`.
- `exchange_core/state.py` with `Account`, `SessionState`, and `EngineState` with `snapshot()` and `restore()`.
- `exchange_core/canonical.py` with `canonical_dict`, `canonical_json`, and `canonical_state_hash` (SHA-256).
- Unit tests in `tests/test_intmath.py` and `tests/test_core_types.py` (33 tests total).
- Gate: `make test` passes.

## [M0] 2026-11-01

### Added
- Repository scaffold: Makefile, pyproject.toml, requirements.txt, Dockerfile.
- Empty Python packages: exchange_core, graders, harness, tools, tests.
- Allowed docs: docs/04_RULEBOOK.md, docs/05_INVARIANTS_AND_DATA.md.
- Placeholder test tests/test_scaffold.py (gate G0).
- tools/publish_allowlist.txt, tools/secrets_scan.py, tools/check_publish.py.
- CI workflow .github/workflows/ci.yml.
- Gate G0: make test passes.
