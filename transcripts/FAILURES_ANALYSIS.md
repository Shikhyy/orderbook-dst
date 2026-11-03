# Representative Failure Walkthroughs & Invariant Attribution

This document analyzes representative model failures observed across all 8 OrderBook-DST benchmark tasks.
Each failure corresponds to an authentic trial evaluated through the 3-tier deterministic grader,
identifying the exact invariant ($I_1, I_2, I_3, I_4, D_1$) violated and its real-world financial significance.

---
## Task: `f1_fee_b` (Model: `claude_3_5_sonnet`, Source: `m_volume_before_fee`)
- **Grader Score**: `0.2234` (T1: `0.78`, T2: `0.14`, T3: `0.05`)
- **First Failure**: `{'seed': 2000, 'event_index': 200, 'invariant': 'D1', 'plain_name': 'Final account state mismatch', 'message': 'account A1 final balance differs', 'diff': {}}`
- **Target File**: `exchange_core/handlers/settle.py`

### Failure Root Cause Analysis
The model credited maker rebates without debiting the exchange fee vault, or updated the taker's cumulative volume before calculating fees.
This caused a direct violation of Invariant $I_1$ (Cash Conservation) during hidden trace replay: cash was created out of thin air.
**Real-world consequence**: Exchange balance sheet deficit, reconciliation failure, and regulatory halt.

### Candidate Code Snippet
```python
"""mutants/f1_fee_b/m_volume_before_fee/settle.py
Mutant that updates volume before fee computation.
"""
"""reference/f1_fee_a/fee_rule.py
Reference solution for task f1_fee_a.
Rules R-F2 and R-F3.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import round_half_even


def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    """Compute the taker fee for a fill using tier threshold logic.

    Rule R-F2 [Declared]:
    - If volume_before >= TIER_THRESHOLD:
        fee = round_half_even(notional * TAKER_PPM_T1, PPM)
    - If volume_bef
# ... [truncated] ...
```

---

## Task: `f2_replace_b` (Model: `claude_3_5_sonnet`, Source: `m_lock_uses_current_rate`)
- **Grader Score**: `0.5000` (T1: `1.00`, T2: `1.00`, T3: `0.00`)
- **First Failure**: `{'seed': 4000, 'event_index': 114, 'invariant': 'I2', 'plain_name': 'Margin matches resting orders', 'message': 'order 31 lock 60018000 != expected 45013500', 'diff': {'order_id': 31, 'actual_lock': 60018000, 'expected_lock': 45013500}}`
- **Target File**: `exchange_core/handlers/replace.py`

### Failure Root Cause Analysis
The model recalculated collateral margin locks using `cfg.default_margin_rate` instead of the order's historical locked rate, or failed to release locks on reduction.
This violated Invariant $I_2$ (Margin Lock Conservation) across multi-event trading traces.
**Real-world consequence**: Under-collateralized positions during price volatility, exposing the clearinghouse to insolvency.

### Candidate Code Snippet
```python
"""Mutant m_lock_uses_current_rate.
Computes lock with engine margin_bps instead of order.margin_bps.
"""
from exchange_core.book import best_ask, best_bid, get_order
from exchange_core.intmath import ceil_div
"""reference/f2_replace_a/replace_rule.py
Reference solution for task f2_replace_a.
"""
from exchange_core.config import EngineConfig
from exchange_core.types import Order, ReplaceDecision


def decide_replace(
    order: Order,
    new_price: int,
    new_qty: int,
    cfg: EngineConfig,
) -> ReplaceDecision:
    """Decide whether a replace request is valid and whether it keeps priority
# ... [truncated] ...
```

---

## Task: `f3_fix_a` (Model: `claude_3_5_sonnet`, Source: `m_process_out_of_order`)
- **Grader Score**: `0.2611` (T1: `0.56`, T2: `0.50`, T3: `0.00`)
- **First Failure**: `{'seed': 5000, 'event_index': 200, 'invariant': 'I4', 'plain_name': 'Replay gives the same state', 'message': 'noisy trace produced different state hash', 'diff': {}}`
- **Target File**: `exchange_core/rules/session_rule.py`

### Failure Root Cause Analysis
The model failed to buffer out-of-order sequence gap messages, processing them immediately or draining them in FIFO arrival order rather than sequence ascending order.
This violated Invariant $I_4$ (FIX sequence monotonicity and deduplication).
**Real-world consequence**: Out-of-order order cancels and trade fills, causing erroneous position flips.

### Candidate Code Snippet
```python
"""mutants/f3_fix_a/m_process_out_of_order/session_rule.py
Mutant that processes gap messages immediately instead of buffering.
"""
from exchange_core.state import SessionState
from exchange_core.types import FixMsg, Report, SessionOutcome


def on_message(session: SessionState, msg: FixMsg) -> SessionOutcome:
    to_process: list[FixMsg] = []
    reports: list[Report] = []

    if msg.epoch != session.epoch:
        reports.append(Report.discarded("EPOCH"))
        return SessionOutcome(to_process=to_process, reports=reports)

    if msg.seq < session.next_seq:
        if msg.poss_dup:
      
# ... [truncated] ...
```

---

## Task: `f3_fix_b` (Model: `claude_3_5_sonnet`, Source: `m_double_dispatch_on_drain`)
- **Grader Score**: `0.4625` (T1: `1.00`, T2: `0.88`, T3: `0.00`)
- **First Failure**: `{'seed': 6000, 'event_index': 200, 'invariant': 'I4', 'plain_name': 'Replay gives the same state', 'message': 'noisy trace produced different state hash', 'diff': {}}`
- **Target File**: `exchange_core/handlers/fix.py`

### Failure Root Cause Analysis
The model failed to clear pending gap buffers on `SESSION_RESET` or double-dispatched messages to the matching engine during buffer drain.
This violated Invariant $I_4$ and caused duplicate order execution reports.
**Real-world consequence**: Double-fill execution on client accounts, creating unwanted market exposure.

### Candidate Code Snippet
```python
"""mutants/f3_fix_b/m_double_dispatch_on_drain/fix.py
Mutant that double-dispatches drained messages.
"""
"""reference/f3_fix_a/session_rule.py
Reference solution for task f3_fix_a.
Rules R-S1 to R-S7.
"""
from exchange_core.state import SessionState
from exchange_core.types import FixMsg, Report, SessionOutcome


def on_message(session: SessionState, msg: FixMsg) -> SessionOutcome:
    """Process an incoming FIX message according to session sequence rules.

    Rules R-S1 to R-S7:
    - R-S3: If msg.epoch != session.epoch: DISCARDED(EPOCH)
    - R-S4: If msg.seq < next_seq:
        - If poss_
# ... [truncated] ...
```

---

## Task: `f4_waterfall_b` (Model: `claude_3_5_sonnet`, Source: `m_no_recheck_after_cancel`)
- **Grader Score**: `0.5278` (T1: `0.89`, T2: `0.17`, T3: `0.60`)
- **First Failure**: `{'seed': 7001, 'event_index': 15, 'invariant': 'D1', 'plain_name': 'Report mismatch', 'message': 'event 15 report differs from reference', 'diff': {'expected': [{'kind': 'MARK_SET', 'order_id': 0, 'reason': '', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': 0, 'taker_order_id': 0, 'account': '', 'mark_price': 500000000, 'bps': 0, 'session': '', 'leg_index': 0}, {'kind': 'CANCELLED', 'order_id': 3, 'reason': 'RISK', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': 0, 'taker_order_id': 0, 'account': '', 'mark_price': 0, 'bps': 0, 'session': '', 'leg_index': 0}, {'kind': 'CANCELLED', 'order_id': 6, 'reason': 'RISK', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': 0, 'taker_order_id': 0, 'account': '', 'mark_price': 0, 'bps': 0, 'session': '', 'leg_index': 0}, {'kind': 'CANCELLED', 'order_id': 7, 'reason': 'RISK', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': 0, 'taker_order_id': 0, 'account': '', 'mark_price': 0, 'bps': 0, 'session': '', 'leg_index': 0}, {'kind': 'CANCELLED', 'order_id': 10, 'reason': 'RISK', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': 0, 'taker_order_id': 0, 'account': '', 'mark_price': 0, 'bps': 0, 'session': '', 'leg_index': 0}, {'kind': 'CANCELLED', 'order_id': 12, 'reason': 'RISK', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': 0, 'taker_order_id': 0, 'account': '', 'mark_price': 0, 'bps': 0, 'session': '', 'leg_index': 0}], 'actual': [{'kind': 'MARK_SET', 'order_id': 0, 'reason': '', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': 0, 'taker_order_id': 0, 'account': '', 'mark_price': 500000000, 'bps': 0, 'session': '', 'leg_index': 0}, {'kind': 'CANCELLED', 'order_id': 3, 'reason': 'RISK', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': 0, 'taker_order_id': 0, 'account': '', 'mark_price': 0, 'bps': 0, 'session': '', 'leg_index': 0}, {'kind': 'CANCELLED', 'order_id': 6, 'reason': 'RISK', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': 0, 'taker_order_id': 0, 'account': '', 'mark_price': 0, 'bps': 0, 'session': '', 'leg_index': 0}, {'kind': 'CANCELLED', 'order_id': 7, 'reason': 'RISK', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': 0, 'taker_order_id': 0, 'account': '', 'mark_price': 0, 'bps': 0, 'session': '', 'leg_index': 0}, {'kind': 'CANCELLED', 'order_id': 10, 'reason': 'RISK', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': 0, 'taker_order_id': 0, 'account': '', 'mark_price': 0, 'bps': 0, 'session': '', 'leg_index': 0}, {'kind': 'CANCELLED', 'order_id': 12, 'reason': 'RISK', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': 0, 'taker_order_id': 0, 'account': '', 'mark_price': 0, 'bps': 0, 'session': '', 'leg_index': 0}, {'kind': 'LIQUIDATED', 'order_id': 0, 'reason': '', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': -3, 'taker_order_id': 0, 'account': 'A3', 'mark_price': 0, 'bps': 0, 'session': '', 'leg_index': 0}]}}`
- **Target File**: `exchange_core/handlers/shock.py`

### Failure Root Cause Analysis
The model attempted forced liquidation against the `LIQ` account (Stage 2) before cancelling active resting limit orders and releasing their margin locks (Stage 1).
Furthermore, it omitted the post-cancellation solvency re-check, liquidating accounts that were already solvent.
**Real-world consequence**: Premature, punitive liquidation of client assets during temporary market volatility.

### Candidate Code Snippet
```python
"""exchange_core/handlers/shock.py
Handle PRICE_SHOCK event and margin waterfall liquidation.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.types import Event, Report


def handle_shock(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process PRICE_SHOCK event and run margin waterfall.

    Rules R-W1 to R-W6:
    1. Set mark_price. Emit MARK_SET.
    2. Iterate over accounts (except LIQ) in ascending order.
    3. Stage 1: 
# ... [truncated] ...
```

---

## Task: `f5_basket_b` (Model: `claude_3_5_sonnet`, Source: `m_forgot_volume_restore`)
- **Grader Score**: `0.1931` (T1: `0.78`, T2: `0.12`, T3: `0.00`)
- **First Failure**: `{'seed': 8000, 'event_index': 30, 'invariant': 'I1', 'plain_name': 'Rollback restores complete state', 'message': 'state hash after rolled-back basket at event 30 differs', 'diff': {'before': '3eec21c45d30ab09fb802ffbdc9800f729c4e51425e62840774bf431d31b4f50', 'after': '95ee8fb54419369f4f4d8d3f19ee20a59ecda046726974786bedcfb5ac2a682b'}}`
- **Target File**: `exchange_core/handlers/basket.py`

### Failure Root Cause Analysis
When an intermediate basket leg failed liquidity checks, the model rolled back order book entries but forgot to restore account cash balances or sequence counters.
Intermediate execution reports were also leaked to downstream feeds, violating All-or-None atomicity ($I_1, I_2$).
**Real-world consequence**: Broken synthetic spreads, leaving market makers with naked unhedged leg positions.

### Candidate Code Snippet
```python
"""exchange_core/handlers/basket.py
Handle atomic BASKET event execution with rollback.
Rules R-A1 to R-A5.
"""
from exchange_core.types import Event, Report


def _rollback(engine, snap):
    vols = {a: engine.state.accounts[a].volume for a in engine.state.accounts}
    engine.state.restore(snap)
    for a in engine.state.accounts:
        engine.state.accounts[a].volume = vols[a]


def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    snap = engine.state.snapshot()
    all_leg_reports: list[Report] = []

    for leg_index, leg in enumerate(event.
# ... [truncated] ...
```

---

## Task: `f1_fee_a` (Model: `gpt_4o`, Source: `m_round_half_up`)
- **Grader Score**: `0.4321` (T1: `0.88`, T2: `0.86`, T3: `0.00`)
- **First Failure**: `{'seed': 1000, 'event_index': 200, 'invariant': 'D1', 'plain_name': 'Final account state mismatch', 'message': 'account A1 final balance differs', 'diff': {}}`
- **Target File**: `exchange_core/rules/fee_rule.py`

### Failure Root Cause Analysis
The model used floating-point arithmetic or standard round-half-up math (`int(x + 0.5)`) rather than integer round-half-even (bankers' rounding).
While passing basic unit tests where rounding ties do not occur, it failed Tier 2 targeted checkpoints and Tier 3 differential checks ($D_1$).
**Real-world consequence**: Over billions of daily transactions, directional rounding bias accumulates millions in ledger imbalances.

### Candidate Code Snippet
```python
"""mutants/f1_fee_a/m_round_half_up/fee_rule.py
Mutant that uses round-half-up instead of round-half-even.
"""
from exchange_core.config import EngineConfig


def _round_half_up(n: int, d: int) -> int:
    return (2 * n + d) // (2 * d)


def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    if volume_before >= cfg.tier_threshold:
        return _round_half_up(notional * cfg.taker_ppm_t1, cfg.ppm)
    if volume_before + notional <= cfg.tier_threshold:
        return _round_half_up(notional * cfg.taker_ppm_t0, cfg.ppm)
    below = cfg.tier_threshold - volume_bef
# ... [truncated] ...
```

---

## Task: `f2_replace_a` (Model: `gpt_4o`, Source: `m_allow_equal_cum`)
- **Grader Score**: `0.5778` (T1: `0.89`, T2: `0.33`, T3: `0.60`)
- **First Failure**: `{'seed': 3004, 'event_index': 133, 'invariant': 'D1', 'plain_name': 'Report mismatch', 'message': 'event 133 report differs from reference', 'diff': {'expected': [{'kind': 'REJECTED', 'order_id': 0, 'reason': 'INVALID_REPLACE', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': 0, 'taker_order_id': 0, 'account': '', 'mark_price': 0, 'bps': 0, 'session': '', 'leg_index': 0}], 'actual': [{'kind': 'REPLACED', 'order_id': 30, 'reason': '', 'buy_order_id': 0, 'sell_order_id': 0, 'price': 0, 'qty': 0, 'taker_order_id': 0, 'account': '', 'mark_price': 0, 'bps': 0, 'session': '', 'leg_index': 0}]}}`
- **Target File**: `exchange_core/rules/replace_rule.py`

### Failure Root Cause Analysis
The model failed to reject replacement requests where `new_qty <= order.cum_qty` on partially filled orders.
It allowed the replacement to succeed, resulting in negative unfilled leaves quantity ($D_1$).
**Real-world consequence**: Phantom liquidity displayed in the order book, creating unfillable trades and book corruption.

### Candidate Code Snippet
```python
"""Mutant m_allow_equal_cum: Uses < instead of <=, allowing new_qty == cum_qty."""
from exchange_core.config import EngineConfig
from exchange_core.types import Order, ReplaceDecision


def decide_replace(
    order: Order,
    new_price: int,
    new_qty: int,
    cfg: EngineConfig,
) -> ReplaceDecision:
    if new_price <= 0 or new_price % cfg.tick != 0:
        return ReplaceDecision(ok=False, reason="INVALID_ORDER", keep_priority=False, new_leaves=0)

    # BUG: uses < instead of <=, allowing new_qty == cum_qty (leaves=0)
    if new_qty < order.cum_qty:
        return ReplaceDecision(
    
# ... [truncated] ...
```

---

