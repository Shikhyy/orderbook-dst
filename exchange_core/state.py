"""exchange_core/state.py
Mutable state classes for the exchange engine.
See docs/05_INVARIANTS_AND_DATA.md.
"""
from dataclasses import dataclass, field

from exchange_core.types import FixMsg, Order


@dataclass
class Account:
    """An account on the exchange.
    Tracks cash balance, locked margin, position, and cumulative volume.
    """
    free_cash: int
    locked_margin: int
    position: int
    volume: int

    def clone(self) -> "Account":
        return Account(
            free_cash=self.free_cash,
            locked_margin=self.locked_margin,
            position=self.position,
            volume=self.volume,
        )


@dataclass
class SessionState:
    """FIX session state.
    Tracks current epoch, expected next sequence number, and out-of-order buffer.
    """
    epoch: int
    next_seq: int
    buffer: dict[int, FixMsg] = field(default_factory=dict)

    def clone(self) -> "SessionState":
        return SessionState(
            epoch=self.epoch,
            next_seq=self.next_seq,
            buffer=dict(self.buffer),
        )


@dataclass
class EngineState:
    """Single container for all mutable engine state.

    Rule ENG-07: The engine must keep all state in one EngineState object.
    Rule ENG-08: EngineState must support snapshot() and restore().
    A restore must give a state with the same hash as the snapshot.
    """
    accounts: dict[str, Account]
    orders: dict[int, Order]  # resting orders by order_id
    fee_vault: int
    next_order_id: int
    next_prio_seq: int
    margin_bps: int
    mark_price: int
    sessions: dict[str, SessionState]
    initial_total: int

    def snapshot(self) -> "EngineState":
        """Produce an independent deep snapshot of the engine state."""
        return EngineState(
            accounts={k: v.clone() for k, v in self.accounts.items()},
            orders={
                k: Order(
                    order_id=v.order_id,
                    account=v.account,
                    side=v.side,
                    price=v.price,
                    qty=v.qty,
                    cum_qty=v.cum_qty,
                    prio_seq=v.prio_seq,
                    margin_bps=v.margin_bps,
                    lock=v.lock,
                    flag=v.flag,
                )
                for k, v in self.orders.items()
            },
            fee_vault=self.fee_vault,
            next_order_id=self.next_order_id,
            next_prio_seq=self.next_prio_seq,
            margin_bps=self.margin_bps,
            mark_price=self.mark_price,
            sessions={k: v.clone() for k, v in self.sessions.items()},
            initial_total=self.initial_total,
        )

    def restore(self, snap: "EngineState") -> None:
        """Restore all state in-place from an earlier snapshot (Rule R-A4, ENG-08)."""
        self.accounts = {k: v.clone() for k, v in snap.accounts.items()}
        self.orders = {
            k: Order(
                order_id=v.order_id,
                account=v.account,
                side=v.side,
                price=v.price,
                qty=v.qty,
                cum_qty=v.cum_qty,
                prio_seq=v.prio_seq,
                margin_bps=v.margin_bps,
                lock=v.lock,
                flag=v.flag,
            )
            for k, v in snap.orders.items()
        }
        self.fee_vault = snap.fee_vault
        self.next_order_id = snap.next_order_id
        self.next_prio_seq = snap.next_prio_seq
        self.margin_bps = snap.margin_bps
        self.mark_price = snap.mark_price
        self.sessions = {k: v.clone() for k, v in snap.sessions.items()}
        self.initial_total = snap.initial_total
