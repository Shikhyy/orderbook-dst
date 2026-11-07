"""exchange_core/handlers/settle.py
Settle trades, fees, and volume.
Rules R-M4, R-F1, R-F2, R-F3. Target for task f1_fee_b.
"""
from exchange_core.types import Fill, Report
from exchange_core.state import EngineState
from exchange_core.intmath import round_half_even
from exchange_core.config import EngineConfig
from exchange_core.ledger import (
    transfer_cash,
    adjust_position,
    pay_fee,
    pay_rebate,
    add_volume,
)

def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:
    """Settle cash, locks, position, volume, and fees for a fill."""
    state: EngineState = engine.state
    cfg: EngineConfig = engine.cfg

    # Step 1: Cash transfer and position update
    notional = fill.notional
    transfer_cash(state, fill.buyer, fill.seller, notional)
    adjust_position(state, fill.buyer, fill.qty)
    adjust_position(state, fill.seller, -fill.qty)

    # Step 2: Compute taker fee based on volume tiers
    taker = fill.buyer if fill.taker_order_id == fill.buy_order_id else fill.seller
    volume_before = state.accounts[taker].volume

    if volume_before >= cfg.TIER_THRESHOLD:
        fee = round_half_even(notional * cfg.TAKER_PPM_T1, cfg.PPM)
    elif volume_before + notional <= cfg.TIER_THRESHOLD:
        fee = round_half_even(notional * cfg.TAKER_PPM_T0, cfg.PPM)
    else:
        below = cfg.TIER_THRESHOLD - volume_before
        above = notional - below
        fee = round_half_even(below * cfg.TAKER_PPM_T0, cfg.PPM) + round_half_even(above * cfg.TAKER_PPM_T1, cfg.PPM)

    # Step 3: Compute maker rebate
    maker = fill.seller if fill.taker_order_id == fill.buy_order_id else fill.buyer
    rebate = round_half_even(notional * cfg.MAKER_REBATE_PPM, cfg.PPM)

    # Step 4: Apply fee and rebate
    pay_fee(state, taker, fee)
    pay_rebate(state, maker, rebate)

    # Step 5: Update volume for both accounts
    add_volume(state, fill.buyer, notional)
    add_volume(state, fill.seller, notional)

    # Step 6: Return FILL report
    return [Report.fill(
        buy_order_id=fill.buy_order_id,
        sell_order_id=fill.sell_order_id,
        price=fill.price,
        qty=fill.qty,
        taker_order_id=fill.taker_order_id,
    )]
