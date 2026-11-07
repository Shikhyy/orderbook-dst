"""exchange_core/handlers/settle.py
Settle trades, fees, and volume.
Rules R-M4, R-F1, R-F2, R-F3.
"""
from exchange_core.intmath import round_half_even
from exchange_core.types import Fill, Report


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:  # type: ignore # noqa: F821
    """Settle cash, position, volume, and fees for a fill."""
    cfg = engine.cfg
    state = engine.state

    buyer = state.accounts[fill.buyer]
    seller = state.accounts[fill.seller]

    if fill.taker_order_id == fill.buy_order_id:
        taker = buyer
        maker = seller
    else:
        taker = seller
        maker = buyer

    notional = fill.notional
    ppm = cfg.ppm
    threshold = cfg.tier_threshold

    volume_before = taker.volume

    # 1-2: cash transfer and position update.
    buyer.free_cash -= notional
    buyer.position += fill.qty
    seller.free_cash += notional
    seller.position -= fill.qty

    # 3: taker fee from the taker's pre-fill volume.
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

    # 4: maker rebate.
    rebate = round_half_even(notional * cfg.maker_rebate_ppm, ppm)

    # 5: collect fee, pay rebate, update vault.
    taker.free_cash -= fee
    maker.free_cash += rebate
    state.fee_vault += fee - rebate

    # 6: volume updates happen after the current fill's fee is computed.
    buyer.volume += notional
    seller.volume += notional

    # 7: emit exactly one FILL report.
    return [
        Report.fill(
            buy_order_id=fill.buy_order_id,
            sell_order_id=fill.sell_order_id,
            price=fill.price,
            qty=fill.qty,
            taker_order_id=fill.taker_order_id,
        )
    ]
