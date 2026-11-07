"""exchange_core/handlers/settle.py
Settle trades, fees, and volume.
Rules R-M4, R-F1, R-F2, R-F3. Target for task f1_fee_b.
"""
from exchange_core.intmath import round_half_even
from exchange_core.types import Fill, Report


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:  # type: ignore # noqa: F821
    """Settle cash, locks, position, volume, and fees for a fill."""
    cfg = engine.cfg
    state = engine.state

    notional = fill.price * fill.qty

    buyer = state.accounts[fill.buyer]
    seller = state.accounts[fill.seller]

    # R-M4 step 1: buyer pays notional, position increases by qty.
    buyer.free_cash -= notional
    buyer.position += fill.qty

    # R-M4 step 2: seller receives notional, position decreases by qty.
    seller.free_cash += notional
    seller.position -= fill.qty

    # The taker is the side whose order id is taker_order_id; the other is maker.
    if fill.taker_order_id == fill.buy_order_id:
        taker_id = fill.buyer
        maker_id = fill.seller
    else:
        taker_id = fill.seller
        maker_id = fill.buyer

    taker = state.accounts[taker_id]
    maker = state.accounts[maker_id]

    # R-M4 step 3 + R-F2: taker fee from taker volume before this fill.
    ppm = cfg.ppm
    threshold = cfg.tier_threshold
    volume_before = taker.volume
    if volume_before >= threshold:
        fee = round_half_even(notional * cfg.taker_ppm_t1, ppm)
    elif volume_before + notional <= threshold:
        fee = round_half_even(notional * cfg.taker_ppm_t0, ppm)
    else:
        below = threshold - volume_before
        above = notional - below
        fee = (
            round_half_even(below * cfg.taker_ppm_t0, ppm)
            + round_half_even(above * cfg.taker_ppm_t1, ppm)
        )

    # R-M4 step 4 + R-F3: maker rebate.
    rebate = round_half_even(notional * cfg.maker_rebate_ppm, ppm)

    # R-M4 step 5: taker pays fee, maker receives rebate, vault gains fee - rebate.
    taker.free_cash -= fee
    maker.free_cash += rebate
    state.fee_vault += fee - rebate

    # R-M4 step 6 + R-F1: buyer and seller each add notional to volume.
    buyer.volume += notional
    seller.volume += notional

    # R-M4 step 7: emit exactly one FILL report.
    return [
        Report.fill(
            buy_order_id=fill.buy_order_id,
            sell_order_id=fill.sell_order_id,
            price=fill.price,
            qty=fill.qty,
            taker_order_id=fill.taker_order_id,
        )
    ]
