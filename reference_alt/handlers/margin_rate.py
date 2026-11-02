"""exchange_core/handlers/margin_rate.py
Handle SET_MARGIN_RATE event.
Rule R-G1.
"""
from typing import Any

from exchange_core.types import Event, Report


def handle_margin_rate(engine: Any, event: Event) -> list[Report]:
    """Handle SET_MARGIN_RATE event.

    Rule R-G1:
    A SET_MARGIN_RATE event sets the margin_bps of the engine.
    It applies to orders accepted after the event only.
    A resting order keeps its stored rate. The engine reports MARGIN_RATE_SET.
    """
    engine.state.margin_bps = event.bps
    return [Report.margin_rate_set(event.bps)]
