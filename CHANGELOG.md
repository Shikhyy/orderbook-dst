# CHANGELOG

## [Unreleased]

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
