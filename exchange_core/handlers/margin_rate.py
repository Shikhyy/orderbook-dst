"""exchange_core/handlers/margin_rate.py
Handle SET_MARGIN_RATE event.
Rule R-G1.
"""
from exchange_core.types import Event, Report


def handle_margin_rate(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Set the engine margin rate.

    Rule R-G1 [Declared]:
    Sets engine margin_bps for future accepted orders.
    Resting orders keep their stored rate.
    Reports MARGIN_RATE_SET.
    """
    engine.state.margin_bps = event.bps
    return [Report.margin_rate_set(event.bps)]
