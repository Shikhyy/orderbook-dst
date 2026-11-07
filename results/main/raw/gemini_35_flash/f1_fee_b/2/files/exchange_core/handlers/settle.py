"""exchange_core/handlers/settle.py
Settle trades, fees, and volume.
Rules R-M4, R-F1, R-F2, R-F3. Target for task f1_fee_b.
"""
from typing import TYPE_CHECKING

from exchange_core.intmath import round_half_even
from exchange_core.types import Fill, Report

if TYPE_CHECKING:
    from exchange_core.engine import Engine


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:
    """Settle cash, locks, position, volume, and fees for a fill."""
    cfg = engine.cfg
    state = engine.state

    notional = fill.notional
    qty = fill.qty

    buyer = state.accounts[fill.buyer]
    seller = state.accounts[fill.seller]

    # Step 1: Buyer pays notional from free_cash. Buyer position increases by qty.
    buyer.free_cash -= notional
    buyer.position += qty

    # Step 2: Seller receives notional in free_cash. Seller position decreases by qty.
    seller.free_cash += notional
    seller.position -= qty

    # Determine taker and maker accounts
    if fill.taker_order_id == fill.buy_order_id:
        taker_acc = buyer
        maker_acc = seller
    else:
        taker_acc = seller
        maker_acc = buyer

    # Step 3: Compute taker fee from taker volume before the fill (R-F2)
    vol_before = taker_acc.volume
    threshold = cfg.tier_threshold
    t0 = cfg.taker_ppm_t0
    t1 = cfg.taker_ppm_t1
    ppm = cfg.ppm

    if vol_before >= threshold:
        fee = round_half_even(notional * t1, ppm)
    elif vol_before + notional <= threshold:
        fee = round_half_even(notional * t0, ppm)
    else:
        below = threshold - vol_before
        above = notional - below
        fee = round_half_even(below * t0, ppm) + round_half_even(above * t1, ppm)

    # Step 4: Compute maker rebate (R-F3)
    rebate = round_half_even(notional * cfg.maker_rebate_ppm, ppm)

    # Step 5: Taker pays fee from free_cash. Maker receives rebate in free_cash.
    # fee_vault increases by fee - rebate.
    taker_acc.free_cash -= fee
    maker_acc.free_cash += rebate
    state.fee_vault += fee - rebate

    # Step 6: Buyer and seller each add notional to their volume (R-F1).
    buyer.volume += notional
    seller.volume += notional

    # Step 7: Return a FILL report.
    report = Report.fill(
        buy_order_id=fill.buy_order_id,
        sell_order_id=fill.sell_order_id,
        price=fill.price,
        qty=fill.qty,
        taker_order_id=fill.taker_order_id,
    )
    return [report]
