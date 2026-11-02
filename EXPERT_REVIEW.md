# EXPERT REVIEW

Independent pre-registration audit and expert review for OrderBook-DST benchmark tasks.
Reviewed prior to candidate model runs per `docs/01_CHARTER.md` section 8 and `docs/12_RESEARCH_PLAN.md`.

---

## 1. Task: f1_fee_a (Family F1, Variant A - Isolated)
- **Target Files**: `exchange_core/rules/fee_rule.py`
- **Applicable Rules**: R-F1, R-F2, R-F3, R-F4
- **Interface**: `compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int`, `compute_maker_rebate(notional: int, cfg: EngineConfig) -> int`
- **difficulty_reason**: AUTHOR TO WRITE
- **Expert Audit**: Verified mathematically against round-half-even specification and threshold splitting logic.

---

## 2. Task: f1_fee_b (Family F1, Variant B - Coupled)
- **Target Files**: `exchange_core/handlers/fill.py`
- **Applicable Rules**: R-F1, R-F2, R-F3, R-F4, R-B5, R-M4
- **Interface**: `settle_fill(engine: Engine, fill: FillEvent) -> list[Report]`
- **difficulty_reason**: AUTHOR TO WRITE
- **Expert Audit**: Verified multi-account ledger updates, maker rebate disbursement from fee vault, and invariant I1 conservation.

---

## 3. Task: f2_replace_a (Family F2, Variant A - Isolated)
- **Target Files**: `exchange_core/rules/replace_rule.py`
- **Applicable Rules**: R-P1, R-P2, R-P3
- **Interface**: `decide_replace(order: Order, new_price: int, new_qty: int, cfg: EngineConfig) -> ReplaceDecision`
- **difficulty_reason**: AUTHOR TO WRITE
- **Expert Audit**: Verified tick validation, cum_qty threshold boundary, and priority retention semantics on quantity decreases.

---

## 4. Task: f2_replace_b (Family F2, Variant B - Coupled)
- **Target Files**: `exchange_core/handlers/replace.py`
- **Applicable Rules**: R-P1, R-P2, R-P3, R-P4, R-P5
- **Interface**: `handle_replace(engine: Engine, event: Event) -> list[Report]`
- **difficulty_reason**: AUTHOR TO WRITE
- **Expert Audit**: Verified margin lock adjustment using stored order margin_bps rate, state priority counter bumping, and ledger synchronization.

---

## 5. Task: f3_fix_a (Family F3, Variant A - Isolated)
- **Target Files**: `exchange_core/rules/fix_rule.py`
- **Applicable Rules**: R-S1, R-S2, R-S3, R-S4, R-S5, R-S6
- **Interface**: `on_message(session: SessionState, msg: FixMsg) -> SessionOutcome`
- **difficulty_reason**: AUTHOR TO WRITE
- **Expert Audit**: Verified sequence gap buffering, duplicate detection ignoring poss_dup for sequencing, and iterative buffer draining.

---

## 6. Task: f3_fix_b (Family F3, Variant B - Coupled)
- **Target Files**: `exchange_core/handlers/fix.py`
- **Applicable Rules**: R-S1, R-S2, R-S3, R-S4, R-S5, R-S6, R-S7
- **Interface**: `handle_fix(engine: Engine, event: Event) -> list[Report]`
- **difficulty_reason**: AUTHOR TO WRITE
- **Expert Audit**: Verified message dispatch loop, recursive/drain body dispatch to core engine handlers, and session state persistence across epochs.

---

## 7. Task: f4_waterfall_b (Family F4, Variant B - Coupled)
- **Target Files**: `exchange_core/handlers/shock.py`
- **Applicable Rules**: R-W1, R-W2, R-W3, R-W4, R-W5, R-W6, R-W7
- **Interface**: `handle_shock(engine: Engine, event: Event) -> list[Report]`
- **difficulty_reason**: AUTHOR TO WRITE
- **Expert Audit**: Verified two-stage breach waterfall: priority-order order cancellations in Stage 1, R-W4 breach re-test, and full liquidation against LIQ in Stage 2.

---

## 8. Task: f5_basket_b (Family F5, Variant B - Coupled)
- **Target Files**: `exchange_core/handlers/basket.py`
- **Applicable Rules**: R-A1, R-A2, R-A3, R-A4, R-A5, R-A6, R-A7
- **Interface**: `handle_basket(engine: Engine, event: Event) -> list[Report]`
- **difficulty_reason**: AUTHOR TO WRITE
- **Expert Audit**: Verified deep state snapshotting prior to leg 1, atomic all-or-none rollback on leg failure, ledger restoration, and intermediate report discard.
