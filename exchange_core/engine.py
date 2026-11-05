"""exchange_core/engine.py
Main engine interface and event dispatcher.
See docs/03_ARCHITECTURE.md and docs/04_RULEBOOK.md.
"""
from exchange_core.canonical import canonical_state_hash
from exchange_core.config import EngineConfig
from exchange_core.handlers.basket import handle_basket
from exchange_core.handlers.cancel import handle_cancel
from exchange_core.handlers.crash import handle_crash
from exchange_core.handlers.fix import handle_fix
from exchange_core.handlers.funding import handle_funding
from exchange_core.handlers.margin_rate import handle_margin_rate
from exchange_core.handlers.new_limit import handle_new_limit
from exchange_core.handlers.replace import handle_replace
from exchange_core.handlers.shock import handle_shock
from exchange_core.state import Account, EngineState
from exchange_core.types import Event, Report


class Engine:
    """The exchange matching engine."""

    def __init__(
        self,
        cfg: EngineConfig,
        accounts: dict[str, int],
        mark_price: int,
    ) -> None:
        """Initialize engine state with configuration, initial accounts, and mark price."""
        self.cfg = cfg
        initial_accounts = {
            acc_id: Account(
                free_cash=start_cash,
                locked_margin=0,
                position=0,
                volume=0,
            )
            for acc_id, start_cash in accounts.items()
        }
        initial_total = sum(accounts.values())
        self.state = EngineState(
            accounts=initial_accounts,
            orders={},
            fee_vault=0,
            next_order_id=1,
            next_prio_seq=1,
            margin_bps=cfg.margin_bps_default,
            mark_price=mark_price,
            sessions={},
            initial_total=initial_total,
        )

    def dispatch(self, event: Event) -> list[Report]:
        """Dispatch an event to its dedicated handler. Rules ENG-04, ENG-05, ENG-06."""
        handlers = {
            "NEW_LIMIT": handle_new_limit,
            "CANCEL": handle_cancel,
            "REPLACE": handle_replace,
            "SET_MARGIN_RATE": handle_margin_rate,
            "PRICE_SHOCK": handle_shock,
            "FIX_MSG": handle_fix,
            "SESSION_RESET": handle_fix,
            "BASKET": handle_basket,
            "FUNDING": handle_funding,
            "PRICE_CRASH": handle_crash,
        }
        handler = handlers.get(event.kind)
        if handler:
            return handler(self, event)
        return [Report.rejected(f"UNKNOWN_EVENT_{event.kind}")]

    def process(self, event: Event) -> list[Report]:
        """Process one input event and return output reports.

        Rule ENG-05, ENG-06.
        """
        return self.dispatch(event)

    def state_hash(self) -> str:
        """Return the canonical SHA-256 state hash.

        Rule ENG-09.
        """
        return canonical_state_hash(self.state)
