PY ?= python3
VENV = .venv
BIN = $(VENV)/bin
# Unbuffered so progress shows when output is redirected to a log file.
export PYTHONUNBUFFERED=1
MODELS ?= models.toml
# Optional subsets, e.g. make feedback TASKS=f1_fee_b,f2_replace_b TRIALS=3
TASKS ?=
TRIALS ?=
# Run only some models from the file, e.g. make run ONLY=gpt_oss_20b,mistral_large
ONLY ?=
EVAL_OPTS = $(if $(TASKS),--tasks $(TASKS),) $(if $(TRIALS),--trials $(TRIALS),) $(if $(ONLY),--only $(ONLY),)

setup:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -r requirements.txt

test:
	$(BIN)/python -m pytest -q tests

lint:
	$(BIN)/python -m ruff check . && $(BIN)/python -m mypy exchange_core graders harness

validate:
	$(BIN)/python tools/validate_graders.py

demo:
	$(BIN)/python tools/make_demo.py

status:
	$(BIN)/python tools/status.py --models $(MODELS)

watch:
	$(BIN)/python tools/status.py --models $(MODELS) --watch

list-models:
	$(BIN)/python tools/list_models.py --models $(MODELS)

pilot:
	$(BIN)/python -m harness.run_eval --models $(MODELS) --mode single_turn --trials 1 --out results/pilot $(if $(TASKS),--tasks $(TASKS),) $(if $(ONLY),--only $(ONLY),)
	PYTHONPATH=. $(BIN)/python harness/report.py --in results/pilot --out results/pilot

run:
	$(BIN)/python -m harness.run_eval --models $(MODELS) --mode single_turn --out results/main $(EVAL_OPTS)

regrade:
	$(BIN)/python -m harness.run_eval --regrade results/main

dry-run:
	$(BIN)/python -m harness.run_eval --models $(MODELS) --mode single_turn --dry-run $(EVAL_OPTS)

feedback:
	$(BIN)/python -m harness.run_eval --models $(MODELS) --mode feedback_loop --out results/feedback $(EVAL_OPTS)

report:
	PYTHONPATH=. $(BIN)/python harness/report.py --in results/main --out results/main
	@if [ -f results/feedback/trials.jsonl ]; then PYTHONPATH=. $(BIN)/python harness/report.py --in results/feedback --out results/feedback; fi

transcripts:
	$(BIN)/python tools/export_transcripts.py --in results/main $(if $(wildcard results/feedback/trials.jsonl),--in results/feedback,) --out transcripts

mutant-tiers:
	$(BIN)/python tools/mutant_tier_analysis.py --out results/grader_analysis

package:
	$(BIN)/python tools/package_zip.py

secrets-scan:
	$(BIN)/python tools/secrets_scan.py

grade-docker:
	$(BIN)/python tools/grade_docker.py

preflight:
	$(BIN)/python tools/preflight.py

audit:
	$(BIN)/python tools/human_audit.py

check-publish:
	$(BIN)/python tools/check_publish.py

.PHONY: setup test lint validate demo status watch list-models pilot run regrade dry-run feedback report transcripts mutant-tiers package secrets-scan check-publish grade-docker preflight audit
