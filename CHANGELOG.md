# CHANGELOG

## [Unreleased]

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
