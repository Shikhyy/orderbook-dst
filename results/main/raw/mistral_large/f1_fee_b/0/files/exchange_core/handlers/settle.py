"""exchange_core/handlers/settle.py
Settle trades, fees, and volume.
Rules R-M4, R-F1, R-F2, R-F3. Target for task f1_fee_b.
"""
from exchange_core.intmath import round_half_even
from exchange_core.types import Fill, Report


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:  # type: ignore # noqa: F821
    """Settle cash, position, volume, fees, rebate, vault, and report for a fill."""
    cfg = engine.cfg
    state = engine.state

    notional = fill.price * fill.qty

    buyer = state.accounts[fill.buyer]
    seller = state.accounts[fill.seller]

    # 1-2: cash transfer and position updates.
    buyer.free_cash -= notional
    buyer.position += fill.qty
    seller.free_cash += notional
    seller.position -= fill.qty

    # Taker is the side whose order initiated the match.
    taker_is_buy = fill.taker_order_id == fill.buy_order_id
    taker = buyer if taker_is_buy else seller
    maker = seller if taker_is_buy else buyer

    # 3: taker fee from taker volume before this fill (R-F2).
    volume_before = taker.volume
    threshold = cfg.tier_threshold
    ppm = cfg.ppm

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

    # 4: maker rebate (R-F3).
    rebate = round_half_even(notional * cfg.maker_rebate_ppm, ppm)

    # 5: taker pays fee, maker receives rebate, vault gets the difference.
    taker.free_cash -= fee
    maker.free_cash += rebate
    state.fee_vault += fee - rebate

    # 6: volume updates after the current fill's fee is computed (R-F1).
    buyer.volume += notional
    seller.volume += notional

    # 7: emit the FILL report.
    return [
        Report.fill(
            buy_order_id=fill.buy_order_id,
            sell_order_id=fill.sell_order_id,
            price=fill.price,
            qty=fill.qty,
            taker_order_id=fill.taker_order_id,
        )
    ]
