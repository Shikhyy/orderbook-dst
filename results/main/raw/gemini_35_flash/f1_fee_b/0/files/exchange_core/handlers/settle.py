"""exchange_core/handlers/settle.py
Settle trades, fees, and volume.
Rules R-M4, R-F1, R-F2, R-F3. Target for task f1_fee_b.
"""
from typing import TYPE_CHECKING

from exchange_core.intmath import round_half_even
from exchange_core.ledger import add_volume, adjust_position, pay_fee, pay_rebate, transfer_cash
from exchange_core.types import Fill, Report

if TYPE_CHECKING:
    from exchange_core.engine import Engine


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:
    """Settle the financial effects of a fill."""
    state = engine.state
    cfg = engine.cfg

    notional = fill.notional

    # Step 1 & 2: Cash transfer and position update
    transfer_cash(state, fill.buyer, fill.seller, notional)
    adjust_position(state, fill.buyer, fill.qty)
    adjust_position(state, fill.seller, -fill.qty)

    # Determine taker and maker accounts
    if fill.taker_order_id == fill.buy_order_id:
        taker_id = fill.buyer
        maker_id = fill.seller
    else:
        taker_id = fill.seller
        maker_id = fill.buyer

    # Step 3: Compute taker fee from taker volume before fill
    vol_before = state.accounts[taker_id].volume
    threshold = cfg.tier_threshold
    ppm = cfg.ppm
    t0 = cfg.taker_ppm_t0
    t1 = cfg.taker_ppm_t1

    if vol_before >= threshold:
        fee = round_half_even(notional * t1, ppm)
    elif vol_before + notional <= threshold:
        fee = round_half_even(notional * t0, ppm)
    else:
        below = threshold - vol_before
        above = notional - below
        fee = round_half_even(below * t0, ppm) + round_half_even(above * t1, ppm)

    # Step 4: Compute maker rebate
    rebate = round_half_even(notional * cfg.maker_rebate_ppm, ppm)

    # Step 5: Taker pays fee, maker receives rebate, fee_vault updated
    pay_fee(state, taker_id, fee)
    pay_rebate(state, maker_id, rebate)

    # Step 6: Buyer and seller each add notional to volume
    add_volume(state, fill.buyer, notional)
    add_volume(state, fill.seller, notional)

    # Step 7: Return FILL report
    report = Report.fill(
        buy_order_id=fill.buy_order_id,
        sell_order_id=fill.sell_order_id,
        price=fill.price,
        qty=fill.qty,
        taker_order_id=fill.taker_order_id,
    )
    return [report]
