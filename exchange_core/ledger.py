"""exchange_core/ledger.py
Cash and lock primitives.
No rule logic belongs here (docs/03_ARCHITECTURE.md).
"""
from typing import Optional

from exchange_core.state import Account, EngineState


def get_account(state: EngineState, account_id: str) -> Optional[Account]:
    """Retrieve an account by ID."""
    return state.accounts.get(account_id)


def has_account(state: EngineState, account_id: str) -> bool:
    """Return True if the account exists."""
    return account_id in state.accounts


def lock_cash(state: EngineState, account_id: str, amount: int) -> None:
    """Move amount from free_cash to locked_margin."""
    acc = state.accounts[account_id]
    acc.free_cash -= amount
    acc.locked_margin += amount


def release_lock(state: EngineState, account_id: str, amount: int) -> None:
    """Move amount from locked_margin to free_cash."""
    acc = state.accounts[account_id]
    acc.locked_margin -= amount
    acc.free_cash += amount


def transfer_cash(state: EngineState, from_id: str, to_id: str, amount: int) -> None:
    """Transfer free_cash from one account to another."""
    state.accounts[from_id].free_cash -= amount
    state.accounts[to_id].free_cash += amount


def adjust_position(state: EngineState, account_id: str, delta: int) -> None:
    """Adjust position by delta (positive = increase, negative = decrease)."""
    state.accounts[account_id].position += delta


def pay_fee(state: EngineState, account_id: str, fee: int) -> None:
    """Deduct fee from account free_cash and deposit to fee_vault."""
    state.accounts[account_id].free_cash -= fee
    state.fee_vault += fee


def pay_rebate(state: EngineState, account_id: str, rebate: int) -> None:
    """Credit rebate from fee_vault to account free_cash."""
    state.fee_vault -= rebate
    state.accounts[account_id].free_cash += rebate


def add_volume(state: EngineState, account_id: str, notional: int) -> None:
    """Add notional to an account's trading volume."""
    state.accounts[account_id].volume += notional
