"""exchange_core/handlers/settle.py
Settle a fill between two orders.
Rules R-M4, R-F1, R-F2, R-F3, R-U2.
"""
from typing import Any

from exchange_core.config import EngineConfig
from exchange_core.intmath import round_half_even
from exchange_core.ledger import (
    add_volume,
    adjust_position,
    pay_fee,
    pay_rebate,
    transfer_cash,
)
from exchange_core.types import Fill, Report

# --- Rule logic (fee_rule), written out here because Variant B code may not
# import exchange_core.rules.* (see the task's 'Allowed imports'). ---

def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    """Compute the taker fee for a fill using tier threshold logic.

    Rule R-F2 [Declared]:
    - If volume_before >= TIER_THRESHOLD:
        fee = round_half_even(notional * TAKER_PPM_T1, PPM)
    - If volume_before + notional <= TIER_THRESHOLD:
        fee = round_half_even(notional * TAKER_PPM_T0, PPM)
    - Otherwise the fill crosses the threshold. Split it:
        below = TIER_THRESHOLD - volume_before
        above = notional - below
        fee = round_half_even(below * T0, PPM) + round_half_even(above * T1, PPM)
    The engine rounds each part on its own. It does not round the sum.
    """
    if volume_before >= cfg.tier_threshold:
        # Rule R-F2: above threshold
        return round_half_even(notional * cfg.taker_ppm_t1, cfg.ppm)

    if volume_before + notional <= cfg.tier_threshold:
        # Rule R-F2: below or exactly on threshold
        return round_half_even(notional * cfg.taker_ppm_t0, cfg.ppm)

    # Rule R-F2: crossing fill split
    below = cfg.tier_threshold - volume_before
    above = notional - below
    fee_below = round_half_even(below * cfg.taker_ppm_t0, cfg.ppm)
    fee_above = round_half_even(above * cfg.taker_ppm_t1, cfg.ppm)
    return fee_below + fee_above


def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
    """Compute the maker rebate for a fill.

    Rule R-F3 [Declared]:
    The maker rebate for a fill is round_half_even(notional * MAKER_REBATE_PPM, PPM).
    """
    return round_half_even(notional * cfg.maker_rebate_ppm, cfg.ppm)


def settle_fill(engine: Any, fill: Fill) -> list[Report]:
    """Apply the financial effects of a fill.

    Rule R-M4:
    1. Buyer pays notional from free_cash, position increases by q.
    2. Seller receives notional in free_cash, position decreases by q.
    3. Settle taker fee and maker rebate (R-F1, R-F2, R-F3).
    4. Return FILL report.
    """
    buyer = fill.buyer
    seller = fill.seller

    if not buyer and fill.buy_order_id in engine.state.orders:
        buyer = engine.state.orders[fill.buy_order_id].account
    if not seller and fill.sell_order_id in engine.state.orders:
        seller = engine.state.orders[fill.sell_order_id].account

    notional = fill.notional
    q = fill.qty

    # 1. Buyer pays notional, position increases by q
    # 2. Seller receives notional, position decreases by q
    transfer_cash(engine.state, buyer, seller, notional)
    adjust_position(engine.state, buyer, q)
    adjust_position(engine.state, seller, -q)

    # 3. Settle fees
    if fill.taker_order_id == fill.buy_order_id:
        taker_acc = buyer
        maker_acc = seller
    else:
        taker_acc = seller
        maker_acc = buyer

    taker_vol_before = engine.state.accounts[taker_acc].volume
    taker_fee = compute_taker_fee(taker_vol_before, notional, engine.cfg)
    maker_rebate = compute_maker_rebate(notional, engine.cfg)

    pay_fee(engine.state, taker_acc, taker_fee)
    pay_rebate(engine.state, maker_acc, maker_rebate)

    add_volume(engine.state, buyer, notional)
    add_volume(engine.state, seller, notional)

    # 4. Report FILL
    return [
        Report.fill(
            buy_order_id=fill.buy_order_id,
            sell_order_id=fill.sell_order_id,
            price=fill.price,
            qty=fill.qty,
            taker_order_id=fill.taker_order_id,
        )
    ]
