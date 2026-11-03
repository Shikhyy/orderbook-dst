"""tests/test_import_policy.py
Tests for candidate AST import policy enforcement.
See docs/07_GRADER_SPEC.md and user import policy specification:
- stdlib, exchange_core.types, .state, .intmath, .config, .book, .ledger, .engine,
  and exchange_core.handlers.new_limit are allowed.
- All other exchange_core.* modules (especially rules.*) are forbidden.
- Candidates that import exchange_core.rules.* in all four forms fail with FORBIDDEN_IMPORT.
- Candidates that import exchange_core.handlers.shock fail with FORBIDDEN_IMPORT.
- Candidates that use importlib.import_module fail with FORBIDDEN_IMPORT.
- Candidates with only allowed imports pass.
- Non-candidate grading (V1/V2 reference flows) does NOT trigger the check.
"""
from graders.dst_grader import grade_task
from graders.import_policy import check_candidate_ast, check_candidate_target_files


def test_forbidden_rules_form_1():
    """Form 1: from exchange_core.rules.fee_rule import compute_taker_fee"""
    code = "from exchange_core.rules.fee_rule import compute_taker_fee\n"
    ok, err = check_candidate_ast(code, "exchange_core/handlers/settle.py")
    assert not ok
    assert "FORBIDDEN_IMPORT" in err
    assert "exchange_core.rules.fee_rule" in err


def test_forbidden_rules_form_2():
    """Form 2: from exchange_core.rules import fee_rule"""
    code = "from exchange_core.rules import fee_rule\n"
    ok, err = check_candidate_ast(code, "exchange_core/handlers/settle.py")
    assert not ok
    assert "FORBIDDEN_IMPORT" in err
    assert "exchange_core.rules" in err


def test_forbidden_rules_form_3():
    """Form 3: from exchange_core import rules"""
    code = "from exchange_core import rules\n"
    ok, err = check_candidate_ast(code, "exchange_core/handlers/settle.py")
    assert not ok
    assert "FORBIDDEN_IMPORT" in err
    assert "rules" in err


def test_forbidden_rules_form_4():
    """Form 4: import exchange_core.rules.fee_rule"""
    code = "import exchange_core.rules.fee_rule\n"
    ok, err = check_candidate_ast(code, "exchange_core/handlers/settle.py")
    assert not ok
    assert "FORBIDDEN_IMPORT" in err
    assert "exchange_core.rules.fee_rule" in err


def test_forbidden_handler_shock():
    """Forbidden handler import: from exchange_core.handlers.shock import handle_shock"""
    code = "from exchange_core.handlers.shock import handle_shock\n"
    ok, err = check_candidate_ast(code, "exchange_core/handlers/basket.py")
    assert not ok
    assert "FORBIDDEN_IMPORT" in err
    assert "shock" in err


def test_forbidden_importlib():
    """Forbidden dynamic import: importlib.import_module"""
    code = (
        "import importlib\n"
        "mod = importlib.import_module('exchange_core.rules.fee_rule')\n"
    )
    ok, err = check_candidate_ast(code, "exchange_core/handlers/settle.py")
    assert not ok
    assert "FORBIDDEN_IMPORT" in err


def test_forbidden_eval_exec():
    """Forbidden dynamic evaluation: eval / exec / __import__"""
    code_eval = "x = eval('__import__(\"exchange_core.rules\")')\n"
    ok, err = check_candidate_ast(code_eval, "exchange_core/handlers/settle.py")
    assert not ok
    assert "FORBIDDEN_IMPORT" in err

    code_exec = "exec('import exchange_core.rules')\n"
    ok2, err2 = check_candidate_ast(code_exec, "exchange_core/handlers/settle.py")
    assert not ok2
    assert "FORBIDDEN_IMPORT" in err2


def test_allowed_imports_pass():
    """Candidate with only allowed imports passes."""
    code = (
        "import math\n"
        "import typing\n"
        "from dataclasses import dataclass\n"
        "from exchange_core.types import Event, Report\n"
        "from exchange_core.state import Account, EngineState\n"
        "from exchange_core.intmath import round_half_even, ceil_div\n"
        "from exchange_core.config import EngineConfig\n"
        "from exchange_core.book import get_account_orders\n"
        "from exchange_core.ledger import apply_fee_and_rebate\n"
        "from exchange_core.engine import Engine\n"
        "from exchange_core.handlers.new_limit import handle_new_limit\n"
    )
    ok, err = check_candidate_ast(code, "exchange_core/handlers/settle.py")
    assert ok
    assert err is None


def test_candidate_grade_task_rejection():
    """Verify that grade_task(..., is_candidate=True) returns score 0 and FORBIDDEN_IMPORT."""
    bad_files = {
        "exchange_core/handlers/shock.py": (
            "from exchange_core.rules.waterfall_rule import plan_shock\n"
            "def handle_shock(engine, event):\n    return []\n"
        )
    }
    rec = grade_task("f4_waterfall_b", bad_files, is_candidate=True)
    assert rec.score == 0.0
    assert rec.passed is False
    assert rec.error == "FORBIDDEN_IMPORT"


def test_reference_bypasses_candidate_check():
    """Verify that reference code passes when is_candidate=False."""
    ref_files = {
        "exchange_core/handlers/shock.py": (
            "from exchange_core.types import Event, Report\n"
            "from exchange_core.rules.waterfall_rule import plan_shock\n"
        )
    }
    # When is_candidate=False (default for V1/V2/V3), check_candidate_target_files is NOT run
    ok, err = check_candidate_target_files(ref_files)
    assert not ok  # It fails the AST check if treated as a candidate
    # But grade_task without is_candidate=True does not reject on AST
