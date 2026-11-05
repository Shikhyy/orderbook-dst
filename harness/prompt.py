"""harness/prompt.py
Prompt builder for OrderBook-DST evaluation harness.
See docs/08_HARNESS_AND_STATS.md sections 2 and 3.
"""
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib as tomli
except ImportError:
    import tomli  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent.parent

SYSTEM_MESSAGE = """You are a senior software engineer. You write Python code.
Follow the rules in the task exactly. Use integer arithmetic only.
Answer with the complete content of each target file.
Use this format for each file:

### FILE: <path>
```python
<complete file content>
```

Write no other text outside these blocks."""

READONLY_CONTEXT_FILES = [
    "exchange_core/types.py",
    "exchange_core/state.py",
    "exchange_core/intmath.py",
    "exchange_core/config.py",
    "exchange_core/book.py",
    "exchange_core/ledger.py",
]

STUB_TEMPLATES: dict[str, str] = {
    "exchange_core/rules/fee_rule.py": '''"""exchange_core/rules/fee_rule.py
Pure functions for taker fee and maker rebate calculation.
Rules R-F2 and R-F3. Target for task f1_fee_a.
"""
from exchange_core.config import EngineConfig


def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    """Compute the taker fee for a fill using tier threshold logic (Rule R-F2)."""
    raise NotImplementedError("Implement compute_taker_fee")


def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
    """Compute the maker rebate for a fill (Rule R-F3)."""
    raise NotImplementedError("Implement compute_maker_rebate")
''',
    "exchange_core/handlers/settle.py": '''"""exchange_core/handlers/settle.py
Settle trades, fees, and volume.
Rules R-M4, R-F1, R-F2, R-F3. Target for task f1_fee_b.
"""
from exchange_core.types import Fill, Report


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:  # type: ignore # noqa: F821
    """Settle cash, locks, position, volume, and fees for a fill."""
    raise NotImplementedError("Implement settle_fill")
''',
    "exchange_core/rules/replace_rule.py": '''"""exchange_core/rules/replace_rule.py
Pure function for replace decisions.
Rules R-P1, R-P2 (steps 2, 3), and R-P3. Target for task f2_replace_a.
"""
from exchange_core.config import EngineConfig
from exchange_core.types import Order, ReplaceDecision


def decide_replace(
    order: Order,
    new_price: int,
    new_qty: int,
    cfg: EngineConfig,
) -> ReplaceDecision:
    """Decide whether a replace request is valid and whether it keeps priority."""
    raise NotImplementedError("Implement decide_replace")
''',
    "exchange_core/handlers/replace.py": '''"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4. Target for task f2_replace_b.
"""
from exchange_core.types import Event, Report


def handle_replace(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a REPLACE event according to rules R-P1 to R-P4."""
    raise NotImplementedError("Implement handle_replace")
''',
    "exchange_core/rules/session_rule.py": '''"""exchange_core/rules/session_rule.py
Pure function for FIX session sequence decisions.
Rules R-S1 to R-S7. Target for task f3_fix_a.
"""
from exchange_core.state import SessionState
from exchange_core.types import Event, SessionOutcome


def on_message(session: SessionState, msg: Event) -> SessionOutcome:
    """Process an incoming FIX message according to session sequence rules."""
    raise NotImplementedError("Implement on_message")
''',
    "exchange_core/handlers/fix.py": '''"""exchange_core/handlers/fix.py
Handler for FIX session messages and session reset.
Rules R-S1 to R-S9. Target for task f3_fix_b.
"""
from exchange_core.types import Event, Report


def handle_fix(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process FIX_MSG and SESSION_RESET events according to rules R-S1 to R-S9."""
    raise NotImplementedError("Implement handle_fix")
''',
    "exchange_core/handlers/shock.py": '''"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from exchange_core.types import Event, Report


def handle_shock(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    raise NotImplementedError("Implement handle_shock")
''',
    "exchange_core/handlers/new_limit.py": '''"""exchange_core/handlers/new_limit.py
Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
"""
from exchange_core.handlers.settle import settle_fill
from exchange_core.types import Event, Report


def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a NEW_LIMIT event."""
    raise NotImplementedError("Implement handle_new_limit")
''',
    "exchange_core/handlers/funding.py": '''"""exchange_core/handlers/funding.py
Handler for FUNDING events: funding payments, fee-vault residual and waterfall.
Rules R-Y1 to R-Y5. Target for task f7_funding_b.
"""
from exchange_core.types import Event, Report


def handle_funding(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a FUNDING event."""
    raise NotImplementedError("Implement handle_funding")
''',
    "exchange_core/handlers/bankruptcy.py": '''"""exchange_core/handlers/bankruptcy.py
Bankruptcy procedure after a liquidation: insurance draw, then loss sharing.
Rules R-L1 to R-L5. Target for task f8_adl_b.
"""
from exchange_core.types import Report


def handle_bankruptcy(
    engine: "Engine", account_id: str, pre_position: int  # type: ignore # noqa: F821
) -> list[Report]:
    """Cover the deficit of a just-liquidated account and return the reports in order."""
    raise NotImplementedError("Implement handle_bankruptcy")
''',
    "exchange_core/handlers/basket.py": '''"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report


def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a BASKET event with all-or-nothing rollback semantics."""
    raise NotImplementedError("Implement handle_basket")
''',
}


@dataclass(frozen=True)
class BuiltPrompt:
    system: str
    user_prompt: str
    prompt_sha256: str


def build_prompt_for_task(task_id: str) -> BuiltPrompt:
    """Build the prompt for a task according to docs/08 section 2."""
    task_dir = REPO_ROOT / "tasks" / task_id
    task_toml = task_dir / "task.toml"
    if not task_toml.exists():
        raise FileNotFoundError(f"task.toml not found for task {task_id}")

    meta: dict[str, Any] = tomli.loads(task_toml.read_text(encoding="utf-8"))
    instruction_file = task_dir / "instruction.md"
    instruction_text = (
        instruction_file.read_text(encoding="utf-8") if instruction_file.exists() else ""
    )

    # A "diagnose and fix" task (mode = "debug", family F9) shows a bug report and the buggy
    # file instead of a stub, and is graded like the task named in `grades_as`.
    is_debug = meta.get("mode") == "debug"
    test_task = str(meta.get("grades_as", task_id)) if is_debug else task_id

    parts: list[str] = []
    # 1. Instruction
    parts.append(instruction_text.strip())

    # 1a. Bug report (debug tasks only)
    if is_debug:
        symptom_file = task_dir / "symptom.md"
        parts.append("\n" + symptom_file.read_text(encoding="utf-8").strip())

    # 1b. Public tests (visible)
    public_test_file = REPO_ROOT / "tasks" / test_task / "public_tests" / f"test_{test_task}.py"
    if public_test_file.exists():
        test_content = public_test_file.read_text(encoding="utf-8")
        parts.append(f"\n## Public Tests (Visible)\n```python\n{test_content.strip()}\n```")

    # 2. Target file stubs (or, for debug tasks, the buggy files)
    target_files = meta.get("target_files", [])
    if is_debug:
        parts.append("\n## Buggy Target Files (return the corrected file)\n")
        for rel_path in target_files:
            buggy_file = task_dir / "buggy" / rel_path
            content = buggy_file.read_text(encoding="utf-8")
            parts.append(f"### Buggy: {rel_path}\n```python\n{content.strip()}\n```")
    else:
        parts.append("\n## Target Files to Implement\n")
    for rel_path in [] if is_debug else target_files:
        stub_file = task_dir / "workspace" / rel_path
        if stub_file.exists():
            content = stub_file.read_text(encoding="utf-8")
        elif rel_path in STUB_TEMPLATES:
            content = STUB_TEMPLATES[rel_path]
        else:
            content = 'raise NotImplementedError("Implement candidate function")\n'

        parts.append(f"### Stub: {rel_path}\n```python\n{content.strip()}\n```")

    # 3. Read-only context files
    parts.append("\n## Reference Context (Read-Only)\n")
    for rel_path in READONLY_CONTEXT_FILES:
        ctx_file = REPO_ROOT / rel_path
        if ctx_file.exists():
            content = ctx_file.read_text(encoding="utf-8")
            parts.append(f"### Context: {rel_path}\n```python\n{content.strip()}\n```")

    user_prompt = "\n\n".join(parts)
    full_text = f"{SYSTEM_MESSAGE}\n\n{user_prompt}"
    sha256 = hashlib.sha256(full_text.encode("utf-8")).hexdigest()

    return BuiltPrompt(
        system=SYSTEM_MESSAGE,
        user_prompt=user_prompt,
        prompt_sha256=sha256,
    )
