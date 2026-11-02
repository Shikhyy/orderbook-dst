PY ?= python3
VENV = .venv
BIN = $(VENV)/bin

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

run:
	$(BIN)/python -m harness.run_eval --models models.toml --mode single_turn --out results/main

regrade:
	$(BIN)/python -m harness.run_eval --regrade results/main

package:
	$(BIN)/python tools/package_zip.py

secrets-scan:
	$(BIN)/python tools/secrets_scan.py

grade-docker:
	$(BIN)/python tools/grade_docker.py

check-publish:
	$(BIN)/python tools/check_publish.py

.PHONY: setup test lint validate demo run regrade package secrets-scan check-publish grade-docker
