"""exchange_core/types.py
Data types and report structures.
See docs/04_RULEBOOK.md and docs/05_INVARIANTS_AND_DATA.md.
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Order:
    """An order in the exchange.

    Rule R-B1: An order has order_id, account, side (BUY or SELL),
    price, qty, cum_qty, prio_seq, margin_bps, lock, flag.
    leaves equals qty - cum_qty. Flag is NONE, IOC, or POST_ONLY.
    """
    order_id: int
    account: str
    side: str
    price: int
    qty: int
    cum_qty: int
    prio_seq: int
    margin_bps: int
    lock: int
    flag: str = "NONE"

    @property
    def leaves(self) -> int:
        return self.qty - self.cum_qty


@dataclass(frozen=True)
class BasketLeg:
    """One leg of an atomic basket event.

    Rule R-A1: A leg has side, price, qty, and flag (IOC or POST_ONLY).
    """
    side: str
    price: int
    qty: int
    flag: str = "NONE"


@dataclass(frozen=True)
class Event:
    """An input event to the exchange engine.

    Events are frozen dataclasses with a kind field.
    Kinds: NEW_LIMIT, CANCEL, REPLACE, SET_MARGIN_RATE, PRICE_SHOCK,
           FIX_MSG, SESSION_RESET, BASKET.
    """
    kind: str
    account: str = ""
    side: str = ""
    price: int = 0
    qty: int = 0
    flag: str = "NONE"
    order_id: int = 0
    new_price: int = 0
    new_qty: int = 0
    bps: int = 0
    mark_price: int = 0
    session: str = ""
    epoch: int = 0
    seq: int = 0
    poss_dup: bool = False
    body: Optional[Any] = None
    legs: tuple[BasketLeg, ...] = field(default_factory=tuple)


# FixMsg alias for FIX sequence handling
FixMsg = Event


@dataclass(frozen=True)
class Report:
    """An output report from the engine.
    See docs/04_RULEBOOK.md section 11.
    """
    kind: str
    order_id: int = 0
    reason: str = ""
    buy_order_id: int = 0
    sell_order_id: int = 0
    price: int = 0
    qty: int = 0
    taker_order_id: int = 0
    account: str = ""
    mark_price: int = 0
    bps: int = 0
    session: str = ""
    leg_index: int = 0

    @classmethod
    def accepted(cls, order_id: int) -> "Report": return cls(kind="ACCEPTED", order_id=order_id)
    @classmethod
    def rejected(cls, reason: str) -> "Report": return cls(kind="REJECTED", reason=reason)
    @classmethod
    def fill(
        cls, buy_order_id: int, sell_order_id: int, price: int, qty: int, taker_order_id: int
    ) -> "Report":
        return cls(
            kind="FILL", buy_order_id=buy_order_id, sell_order_id=sell_order_id,
            price=price, qty=qty, taker_order_id=taker_order_id,
        )
    @classmethod
    def cancelled(cls, order_id: int, reason: str) -> "Report":
        return cls(kind="CANCELLED", order_id=order_id, reason=reason)
    @classmethod
    def replaced(cls, order_id: int) -> "Report": return cls(kind="REPLACED", order_id=order_id)
    @classmethod
    def buffered(cls) -> "Report": return cls(kind="BUFFERED")
    @classmethod
    def discarded(cls, reason: str) -> "Report": return cls(kind="DISCARDED", reason=reason)
    @classmethod
    def liquidated(cls, account: str, qty: int) -> "Report":
        return cls(kind="LIQUIDATED", account=account, qty=qty)
    @classmethod
    def mark_set(cls, mark_price: int) -> "Report":
        return cls(kind="MARK_SET", mark_price=mark_price)
    @classmethod
    def margin_rate_set(cls, bps: int) -> "Report": return cls(kind="MARGIN_RATE_SET", bps=bps)
    @classmethod
    def session_reset_done(cls, session: str) -> "Report":
        return cls(kind="SESSION_RESET_DONE", session=session)
    @classmethod
    def basket_committed(cls) -> "Report": return cls(kind="BASKET_COMMITTED")
    @classmethod
    def basket_rolled_back(cls, leg_index: int) -> "Report":
        return cls(kind="BASKET_ROLLED_BACK", leg_index=leg_index)


@dataclass(frozen=True)
class Fill:
    """Internal fill record passed to settle_fill."""
    buy_order_id: int
    sell_order_id: int
    price: int
    qty: int
    taker_order_id: int
    buyer: str = ""
    seller: str = ""

    @property
    def notional(self) -> int:
        return self.price * self.qty


@dataclass
class ReplaceDecision:
    """Outcome of pure replace rule (Variant A target)."""
    ok: bool
    reason: str = ""
    keep_priority: bool = False
    new_leaves: int = 0


@dataclass
class SessionOutcome:
    """Outcome of pure session message handling (Variant A target)."""
    to_process: list[Any] = field(default_factory=list)
    reports: list[Report] = field(default_factory=list)


@dataclass
class AccountView:
    """Read-only view of account for waterfall planning."""
    account_id: str
    free_cash: int
    locked_margin: int
    position: int


@dataclass
class WaterfallPlan:
    """Outcome of pure waterfall planning (Variant A target)."""
    in_breach_stage1: bool
    in_breach_stage2: bool
    cancelled_orders: list[int] = field(default_factory=list)
    liquidate_qty: int = 0
