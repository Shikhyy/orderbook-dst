"""exchange_core/handlers/settle.py
Settle trades, fees, and volume.
Rules R-M4, R-F1, R-F2, R-F3. Target for task f1_fee_b.
"""
from exchange_core.types import Fill, Report
from exchange_core.intmath import round_half_even
from exchange_core.ledger import (
    transfer_cash,
    adjust_position,
    pay_fee,
    pay_rebate,
    add_volume,
    get_account,
)


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:  # type: ignore # noqa: F821
    """Settle cash, locks, position, volume, and fees for a fill."""
    state = engine.state
    cfg = engine.cfg
    
    buyer_id = fill.buyer
    seller_id = fill.seller
    notional = fill.notional  # price * qty
    
    # 1. Buyer pays notional, seller receives notional
    transfer_cash(state, buyer_id, seller_id, notional)
    
    # 2. Update positions: buyer +qty, seller -qty
    adjust_position(state, buyer_id, fill.qty)
    adjust_position(state, seller_id, -fill.qty)
    
    # 3. Determine taker and maker
    if fill.taker_order_id == fill.buy_order_id:
        taker_id = buyer_id
        maker_id = seller_id
    else:
        taker_id = seller_id
        maker_id = buyer_id
    
    # 4. Compute taker fee using volume BEFORE the fill (R-F2)
    taker_account = get_account(state, taker_id)
    volume_before = taker_account.volume
    
    fee = _compute_taker_fee(notional, volume_before, cfg)
    
    # 5. Compute maker rebate (R-F3)
    rebate = _compute_maker_rebate(notional, cfg)
    
    # 6. Taker pays fee, maker receives rebate, vault += fee - rebate
    pay_fee(state, taker_id, fee)
    pay_rebate(state, maker_id, rebate)
    
    # 7. Add notional to BOTH buyer and seller volume (R-F1)
    add_volume(state, buyer_id, notional)
    add_volume(state, seller_id, notional)
    
    # 8. Return FILL report
    return [Report.fill(
        buy_order_id=fill.buy_order_id,
        sell_order_id=fill.sell_order_id,
        price=fill.price,
        qty=fill.qty,
        taker_order_id=fill.taker_order_id,
    )]


def _compute_taker_fee(notional: int, volume_before: int, cfg: "EngineConfig") -> int:
    """Compute taker fee according to R-F2 with tiered rates."""
    threshold = cfg.TIER_THRESHOLD
    t0 = cfg.TAKER_PPM_T0
    t1 = cfg.TAKER_PPM_T1
    ppm = cfg.PPM
    
    if volume_before >= threshold:
        # Entire notional at T1 rate
        return round_half_even(notional * t1, ppm)
    elif volume_before + notional <= threshold:
        # Entire notional at T0 rate
        return round_half_even(notional * t0, ppm)
    else:
        # Crosses threshold: split at threshold
        below = threshold - volume_before
        above = notional - below
        fee_below = round_half_even(below * t0, ppm)
        fee_above = round_half_even(above * t1, ppm)
        return fee_below + fee_above


def _compute_maker_rebate(notional: int, cfg: "EngineConfig") -> int:
    """Compute maker rebate according to R-F3."""
    return round_half_even(notional * cfg.MAKER_REBATE_PPM, cfg.PPM)
