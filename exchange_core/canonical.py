"""exchange_core/canonical.py
Canonical JSON formatting and state hash computation.
See docs/05_INVARIANTS_AND_DATA.md section 5.
"""
import hashlib
import json
from typing import Any

from exchange_core.state import Account, EngineState, SessionState
from exchange_core.types import Order


def _account_to_dict(acc: Account) -> dict[str, int]:
    return {
        "free_cash": acc.free_cash,
        "locked_margin": acc.locked_margin,
        "position": acc.position,
        "volume": acc.volume,
    }


def _order_to_dict(order: Order) -> dict[str, Any]:
    fields = (
        "order_id", "account", "side", "price", "qty", "cum_qty",
        "prio_seq", "margin_bps", "lock", "flag",
    )
    return {k: getattr(order, k) for k in fields}


def _msg_to_dict(msg: Any) -> dict[str, Any]:
    if msg is None:
        return {}
    if hasattr(msg, "__dict__"):
        d = dict(msg.__dict__)
        if "body" in d and d["body"] is not None and hasattr(d["body"], "__dict__"):
            d["body"] = dict(d["body"].__dict__)
        return d
    return dict(msg)


def _session_to_dict(session: SessionState) -> dict[str, Any]:
    return {
        "epoch": session.epoch,
        "next_seq": session.next_seq,
        "buffer": {
            seq: _msg_to_dict(session.buffer[seq])
            for seq in sorted(session.buffer.keys())
        },
    }


def canonical_dict(state: EngineState) -> dict[str, Any]:
    """Build the canonical dictionary for state serialization.

    Rule docs/05 section 5:
    1. Keys: accounts, orders, fee_vault, next_order_id, next_prio_seq,
             margin_bps, mark_price, sessions.
    2. Sort accounts by id. Sort orders by order_id. Sort sessions by id.
       Sort buffers by seq.
    """
    return {
        "accounts": {
            acc_id: _account_to_dict(state.accounts[acc_id])
            for acc_id in sorted(state.accounts.keys())
        },
        "orders": {
            oid: _order_to_dict(state.orders[oid])
            for oid in sorted(state.orders.keys())
        },
        "fee_vault": state.fee_vault,
        "next_order_id": state.next_order_id,
        "next_prio_seq": state.next_prio_seq,
        "margin_bps": state.margin_bps,
        "mark_price": state.mark_price,
        "sessions": {
            s_id: _session_to_dict(state.sessions[s_id])
            for s_id in sorted(state.sessions.keys())
        },
    }


def canonical_json(state: EngineState) -> str:
    """Convert state to canonical JSON string with sorted keys and minimal separators."""
    d = canonical_dict(state)
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_state_hash(state: EngineState) -> str:
    """Compute the SHA-256 state hash from canonical JSON (Rule ENG-09, docs/05 section 5)."""
    raw_json = canonical_json(state)
    return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
