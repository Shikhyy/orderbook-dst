"""Margin rate handler.

Rule R-G1:
- A SET_MARGIN_RATE event sets the margin_bps of the engine.
- Applies to orders accepted after the event only.
- Resting orders keep stored rate.
- Reports MARGIN_RATE_SET.
"""
from typing import Any

from exchange_core.types import Event, Report


def handle_margin_rate(engine: Any, event: Event) -> list[Report]:
    """Handle a SET_MARGIN_RATE event.

    Rule R-G1:
    Sets the margin_bps of the engine. Applies to orders accepted after only.
    Reports MARGIN_RATE_SET.
    """
    engine.state.margin_bps = event.bps
    return [Report.margin_rate_set(event.bps)]
