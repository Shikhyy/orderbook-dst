# CHANGELOG

## [Unreleased]

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
