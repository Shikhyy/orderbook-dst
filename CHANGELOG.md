# CHANGELOG

## [Unreleased]

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
