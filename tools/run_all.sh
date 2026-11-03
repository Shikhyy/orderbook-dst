#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Resolve Python binary
PY="python3"
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
    PY="$REPO_ROOT/.venv/bin/python"
fi

echo "================================================================================"
echo "ORDERBOOK-DST BENCHMARK EVALUATION RUNNER"
echo "================================================================================"
echo "Repository: $REPO_ROOT"
echo "Python:     $PY"
echo ""

# 1. Run Preflight Checklist
echo "--------------------------------------------------------------------------------"
echo "STEP 1: Running Preflight Checklist Verification"
echo "--------------------------------------------------------------------------------"
"$PY" tools/preflight.py || {
    echo ""
    echo "WARNING: Preflight checklist reported failures."
    echo "Please resolve checklist items before running candidate model evaluations."
}

echo ""
echo "--------------------------------------------------------------------------------"
echo "STEP 2: Checking models.toml Configuration"
echo "--------------------------------------------------------------------------------"
if [ ! -f "models.toml" ]; then
    echo "models.toml not found."
    echo ""
    echo "To configure candidate models:"
    echo "  1. cp models.example.toml models.toml"
    echo "  2. Edit models.toml with target frontier and baseline model IDs."
    echo "  3. Configure API keys in your environment or .env (e.g. ANTHROPIC_API_KEY, OPENAI_API_KEY)."
    echo ""
    echo "DRY-RUN PROJECTION (Using models.example.toml template):"
    "$PY" -m harness.run_eval --models models.example.toml --mode single_turn --trials 1 --dry-run || true
    echo ""
    echo "DRY-RUN PROJECTION FOR MAIN EVALUATION (5 trials, models.example.toml):"
    "$PY" -m harness.run_eval --models models.example.toml --mode single_turn --trials 5 --dry-run || true
    exit 0
fi

echo "models.toml detected."
echo ""
echo "--------------------------------------------------------------------------------"
echo "STEP 3: Pilot Evaluation Run (1 Trial per Task) -- DRY RUN"
echo "--------------------------------------------------------------------------------"
"$PY" -m harness.run_eval --models models.toml --mode single_turn --trials 1 --dry-run

echo ""
echo "--------------------------------------------------------------------------------"
echo "STEP 4: Pilot Execution Confirmation"
echo "--------------------------------------------------------------------------------"
read -r -p "Execute pilot evaluation run (1 trial per task) now? [yes/NO]: " confirm_pilot
if [ "$confirm_pilot" = "yes" ]; then
    echo "Executing pilot run..."
    "$PY" -m harness.run_eval --models models.toml --mode single_turn --trials 1 --out results/pilot
    echo "Pilot evaluation complete. Results written to results/pilot/."
else
    echo "Pilot execution skipped."
fi

echo ""
echo "--------------------------------------------------------------------------------"
echo "STEP 5: Main Evaluation Run (5 Trials per Task) -- DRY RUN COST PROJECTION"
echo "--------------------------------------------------------------------------------"
"$PY" -m harness.run_eval --models models.toml --mode single_turn --trials 5 --dry-run

echo ""
echo "To execute the main benchmark evaluation when ready, run:"
echo "  $PY -m harness.run_eval --models models.toml --mode single_turn --trials 5 --out results/main"
echo "or:"
echo "  make run"
echo "================================================================================"
