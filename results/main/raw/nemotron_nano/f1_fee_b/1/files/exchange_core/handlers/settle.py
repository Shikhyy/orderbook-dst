"""exchange_core/handlers/settle.py
Settle trades, fees, and volume.
Rules R-M4, R-F1, R-F2, R-F3. Target for task f1_fee_b.
"""
from exchange_core.types import Fill, Report
from exchange_core.ledger import adjust_position, pay_fee, pay_rebate, add_volume


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:
    """Settle cash, locks, position, volume, and fees for a fill."""
    # Identify taker account
    taker_order = engine.orders[fill.taker_order_id]
    taker_account_id = taker_order.account
    taker_acc = engine.state.accounts[taker_account_id]

    # Notional value of the fill
    notional = fill.price * fill.qty

    # Volume of the taker before this fill
    volume_before = taker_acc.volume

    # Compute taker fee according to R-F2
    tier_threshold = engine.cfg.TIER_THRESHOLD
    taker_ppm_t0 = engine.cfg.TAKER_PPM_T0
    taker_ppm_t1 = engine.cfg.TAKER_PPM_T1
    ppm = engine.cfg.PPM

    if volume_before >= tier_threshold:
        fee = round_half_even(notional * taker_ppm_t1, ppm)
    elif volume_before + notional <= tier_threshold:
        fee = round_half_even(notional * taker_ppm_t0, ppm)
    else:
        below = tier_threshold - volume_before
        above = notional - below
        fee = (
            round_half_even(below * taker_ppm_t0, ppm)
            + round_half_even(above * taker_ppm_t1, ppm)
        )

    # Compute maker rebate according to R-F3
    maker_rebate_ppm = engine.cfg.MAKER_REBATE_PPM
    rebate = round_half_even(notional * maker_rebate_ppm, ppm)

    # Cash transfers and position updates
    buyer_acc = engine.state.accounts[fill.buyer]
    seller_acc = engine.state.accounts[fill.seller]

    # Buyer pays notional and increases position
    buyer_acc.free_cash -= notional
    adjust_position(engine, fill.buyer, fill.qty)

    # Seller receives notional and decreases position
    seller_acc.free_cash += notional
    adjust_position(engine, fill.seller, -fill.qty)

    # Pay fee and rebate
    pay_fee(engine, taker_account_id, fee)
    pay_rebate(engine, fill.seller, rebate)

    # Update trading volume (R-F1)
    add_volume(engine, fill.buyer, notional)
    add_volume(engine, fill.seller, notional)

    # Emit the FILL report
    return [Report.fill(fill.buy_order_id, fill.sell_order_id, fill.price, fill.qty, fill.taker_order_id)]
