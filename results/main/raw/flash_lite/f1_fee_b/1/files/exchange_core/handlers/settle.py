"""exchange_core/handlers/settle.py
Settle trades, fees, and volume.
Rules R-M4, R-F1, R-F2, R-F3. Target for task f1_fee_b.
"""
from exchange_core.types import Fill, Report
from exchange_core.intmath import round_half_even
from exchange_core.ledger import transfer_cash, adjust_position, pay_fee, pay_rebate, add_volume


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:  # type: ignore # noqa: F821
    """Settle cash, locks, position, volume, and fees for a fill."""
    notional = fill.notional
    taker_account = fill.buyer if fill.taker_order_id == fill.buy_order_id else fill.seller
    maker_account = fill.seller if fill.taker_order_id == fill.buy_order_id else fill.buyer

    # 1. Buyer pays notional, position increases
    transfer_cash(engine.state, fill.buyer, fill.seller, notional)
    adjust_position(engine.state, fill.buyer, fill.qty)
    # 2. Seller position decreases
    adjust_position(engine.state, fill.seller, -fill.qty)

    # 3. Compute taker fee from taker volume before the fill
    taker_vol = engine.state.accounts[taker_account].volume
    threshold = engine.cfg.TIER_THRESHOLD
    ppm = engine.cfg.PPM
    
    if taker_vol >= threshold:
        fee = round_half_even(notional * engine.cfg.TAKER_PPM_T1, ppm)
    elif taker_vol + notional <= threshold:
        fee = round_half_even(notional * engine.cfg.TAKER_PPM_T0, ppm)
    else:
        below = threshold - taker_vol
        above = notional - below
        fee = round_half_even(below * engine.cfg.TAKER_PPM_T0, ppm) + \
              round_half_even(above * engine.cfg.TAKER_PPM_T1, ppm)

    # 4. Compute maker rebate
    rebate = round_half_even(notional * engine.cfg.MAKER_REBATE_PPM, ppm)

    # 5. Taker pays fee, Maker receives rebate, Vault updates
    pay_fee(engine.state, taker_account, fee)
    pay_rebate(engine.state, maker_account, rebate)

    # 6. Add to volume
    add_volume(engine.state, fill.buyer, notional)
    add_volume(engine.state, fill.seller, notional)

    # 7. Return report
    return [Report.fill(
        buy_order_id=fill.buy_order_id,
        sell_order_id=fill.sell_order_id,
        price=fill.price,
        qty=fill.qty,
        taker_order_id=fill.taker_order_id,
    )]
