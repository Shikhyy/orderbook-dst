"""mutants/f1_fee_b/m_vault_not_updated/settle.py
Mutant that fails to update the fee vault. Violates I1.
"""
from exchange_core.rules.fee_rule import compute_maker_rebate, compute_taker_fee
from exchange_core.types import Fill, Report


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:  # type: ignore # noqa: F821
    state = engine.state
    cfg = engine.cfg
    notional = fill.notional

    state.accounts[fill.buyer].free_cash -= notional
    state.accounts[fill.buyer].position += fill.qty

    state.accounts[fill.seller].free_cash += notional
    state.accounts[fill.seller].position -= fill.qty

    if fill.taker_order_id == fill.buy_order_id:
        taker_acc = fill.buyer
        maker_acc = fill.seller
    else:
        taker_acc = fill.seller
        maker_acc = fill.buyer

    volume_before = state.accounts[taker_acc].volume
    fee = compute_taker_fee(volume_before, notional, cfg)
    rebate = compute_maker_rebate(notional, cfg)

    state.accounts[taker_acc].free_cash -= fee
    state.accounts[maker_acc].free_cash += rebate
    # Mutant bug: state.fee_vault is not updated

    state.accounts[fill.buyer].volume += notional
    state.accounts[fill.seller].volume += notional

    return [
        Report.fill(
            buy_order_id=fill.buy_order_id,
            sell_order_id=fill.sell_order_id,
            price=fill.price,
            qty=fill.qty,
            taker_order_id=fill.taker_order_id,
        )
    ]
