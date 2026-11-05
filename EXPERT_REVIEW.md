# EXPERT REVIEW

Independent pre-registration audit and expert domain review for OrderBook-DST benchmark tasks.
Authored and reviewed prior to candidate model runs per `docs/04_RULEBOOK.md` and `docs/05_INVARIANTS_AND_DATA.md`.

---

## 1. Task: f1_fee_a (Family F1, Variant A - Isolated)
- **Target Files**: `exchange_core/rules/fee_rule.py`
- **Applicable Rules**: R-F1, R-F2, R-F3, R-F4
- **Interface**: `compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int`, `compute_maker_rebate(notional: int, cfg: EngineConfig) -> int`
- **Difficulty Reason**: Requires piecewise rate interpolation across 30-day cumulative volume tier thresholds, applying independent round-half-even (bankers' rounding) ties to each fill segment with zero floating-point imprecision (R-F1, R-F2, R-F4).
- **Author Audit**:
  - *Domain Rationale*: Fee scheduling in production exchanges (e.g. CME, Coinbase, Binance) employs tiered fee ladders based on rolling 30-day trader turnover. When a single large execution spans across volume tier boundaries, standard practice requires splitting the execution notional into distinct sub-segments corresponding to each tier.
  - *Mathematical Precision*: The critical failure trap is applying a single average rate or applying the ending tier rate to the entire trade. Under rule R-F2, each segment must be calculated separately using fixed-point scaled basis points ($\text{fee\_rate} / 10{,}000$). Bankers' rounding (IEEE 754 round-half-even) is strictly enforced on each segment: halves round to the nearest even integer, preventing cumulative directional drift over millions of daily fills.
  - *Invariant Exposure*: Violations in integer division or tie handling directly induce accounting drift in exchange reconciliation ($I_1$).

---

## 2. Task: f1_fee_b (Family F1, Variant B - Coupled)
- **Target Files**: `exchange_core/handlers/settle.py`
- **Applicable Rules**: R-F1, R-F2, R-F3, R-F4, R-B5, R-M4
- **Interface**: `settle_fill(engine: Engine, fill: FillEvent) -> list[Report]`
- **Difficulty Reason**: Requires orchestrating multi-account ledger transfers with strict fee vault balance conservation: maker rebates must be funded strictly from accumulated taker fees, and 30-day account volume must update strictly after fee calculation (R-F1 to R-F4, R-B5, R-M4).
- **Author Audit**:
  - *Domain Rationale*: Trade settlement is the core clearing engine operation. When two orders cross, cash and positions must clear bilaterally between buyer and seller, but maker-taker economics introduce an asymmetric cash flow: the maker receives a rebate while the taker pays a fee.
  - *Coupled Subsystem Hazards*: The exchange fee vault acts as the liquidity pool that accumulates net fee revenue ($\text{taker\_fee} - \text{maker\_rebate}$). If candidate code credits the maker's cash without debiting the fee vault, or debits taker cash without crediting the vault, total system cash ceases to be conserved ($I_1$). Furthermore, per rule R-B5, the taker's cumulative 30-day volume must update *after* the fee calculation; mutating volume beforehand prematurely bumps the trader into a lower fee tier.
  - *Report Ordering*: Per contract specification, `settle_fill` must return a single `Report.fill` report with accurate fee, rebate, and cash balance fields.

---

## 3. Task: f2_replace_a (Family F2, Variant A - Isolated)
- **Target Files**: `exchange_core/rules/replace_rule.py`
- **Applicable Rules**: R-P1, R-P2, R-P3
- **Interface**: `decide_replace(order: Order, new_price: int, new_qty: int, cfg: EngineConfig) -> ReplaceDecision`
- **Difficulty Reason**: Requires enforcing asymmetric price-time priority rules where price changes and quantity increases lose priority while quantity reductions retain it, strictly rejecting replacements where new_qty <= cum_qty on partial fills (R-P1 to R-P3).
- **Author Audit**:
  - *Domain Rationale*: Order Cancel/Replace (FIX tag 35=G) is the highest-volume message type on electronic exchanges (representing >80% of order flow from market makers). Priority preservation rules dictate competitive queuing dynamics.
  - *Asymmetry Analysis*: Under rule R-P1, a trader reducing quote size (`new_qty < order.qty`) does not harm other market participants and thus retains original queue priority timestamp (`retain_priority = True`). Conversely, increasing quote size or modifying the limit price grants an unfair advantage unless the order is placed at the back of the queue (`retain_priority = False`).
  - *Boundary Traps*: For partially filled resting orders, candidate code must verify `new_qty > order.cum_qty`. If `new_qty <= order.cum_qty`, the replace must be rejected (`REJECTED`) rather than accepted or cancelled, preventing zombie orders or negative unfilled leaves quantities.

---

## 4. Task: f2_replace_b (Family F2, Variant B - Coupled)
- **Target Files**: `exchange_core/handlers/replace.py`
- **Applicable Rules**: R-P1, R-P2, R-P3, R-P4, R-U3
- **Interface**: `handle_replace(engine: Engine, event: Event) -> list[Report]`
- **Difficulty Reason**: Couples in-flight book queue updates with account margin lock adjustments: margin must be recalculated using the order's original locked rate rather than the engine default, with atomic rejection and rollback on insufficient funds (R-P1 to R-P5).
- **Author Audit**:
  - *Domain Rationale*: Handling replace events at the engine level links the book matching queue, the order state store, and the collateral margin ledger into a single atomic transaction.
  - *Margin Lock Conservation*: When an order's quantity or price is modified, the collateral locked against that order must adjust. Under rule R-P4, the margin calculation must use the order's historical `margin_rate` captured at order entry rather than a newly updated global configuration rate, ensuring deterministic capital allocation. If the account lacks sufficient free cash for an upward adjustment, the replace must reject cleanly with zero mutations to the order book queue or account balance ($I_2$).
  - *Priority Desynchronization*: If priority is lost, the order must be removed and re-inserted into the book queue with a newly incremented engine priority sequence counter ($I_3$).

---

## 5. Task: f3_fix_a (Family F3, Variant A - Isolated)
- **Target Files**: `exchange_core/rules/session_rule.py`
- **Applicable Rules**: R-S1, R-S2, R-S3, R-S4, R-S5, R-S6, R-S7
- **Interface**: `on_message(session: SessionState, msg: FixMsg) -> SessionOutcome`
- **Difficulty Reason**: Implements stateful FIX session sequence processing: detects out-of-order sequence gaps, buffers gap messages, and drains them in strict sequence ascending order upon gap recovery while validating PossDupFlag(43) semantics (R-S1 to R-S6).
- **Author Audit**:
  - *Domain Rationale*: The Financial Information eXchange (FIX) protocol is the universal messaging backbone of institutional capital markets. Strict sequence number processing prevents out-of-order execution, dropped trades, and duplicate executions.
  - *Protocol Invariants*: Each inbound message carries a sequence number `msg_seq_num`. If `msg_seq_num == session.next_in_seq`, the message is processed immediately. If `msg_seq_num > session.next_in_seq`, a gap is detected: the message must be buffered and a `ResendRequest` generated (R-S2). Crucially, when missing messages arrive, the session buffer must drain in strictly ascending sequence order (R-S4).
  - *PossDup Semantics*: Messages arriving with sequence number below `next_in_seq` must be rejected unless marked with `PossDupFlag(43)=Y`. Even with `PossDupFlag=Y`, duplicate messages must not re-execute business logic if already processed ($I_4$).

---

## 6. Task: f3_fix_b (Family F3, Variant B - Coupled)
- **Target Files**: `exchange_core/handlers/fix.py`
- **Applicable Rules**: R-S1, R-S2, R-S3, R-S4, R-S5, R-S6, R-S7, R-S8, R-S9
- **Interface**: `handle_fix(engine: Engine, event: Event) -> list[Report]`
- **Difficulty Reason**: Couples FIX protocol sequencing with core matching engine event dispatch: enforces session reset epochs, clears message buffers on reset, and guarantees zero duplicate dispatches during out-of-order buffer drains (R-S1 to R-S7).
- **Author Audit**:
  - *Domain Rationale*: Integrating the session protocol handler with the matching engine dispatch loop requires precise state management across session resets and sequence renegotiation.
  - *Epoch and Reset Invariants*: On `SESSION_RESET`, the session's sequence numbers reset to 1, and the session epoch increments. Candidate code must purge pending gap buffers from prior sessions to prevent phantom messages from bleeding into the new session.
  - *Dispatch Ordering*: Drained messages from the gap buffer must be dispatched through `engine.dispatch` in exact sequence order. Double-dispatching or dispatching unbuffered duplicates causes critical order book state corruption and duplicate execution reports ($I_4$).

---

## 7. Task: f4_waterfall_b (Family F4, Variant B - Coupled)
- **Target Files**: `exchange_core/handlers/shock.py`
- **Applicable Rules**: R-W1, R-W2, R-W3, R-W4, R-W5, R-W6
- **Interface**: `handle_shock(engine: Engine, event: Event) -> list[Report]`
- **Difficulty Reason**: Implements a two-stage margin liquidation waterfall: Stage 1 cancels resting orders in priority order and releases locked margin with post-cancellation solvency rechecks, before Stage 2 forced transfers to the LIQ account (R-W1 to R-W7).
- **Author Audit**:
  - *Domain Rationale*: Market-wide price shocks threaten exchange clearinghouse solvency (e.g. LME Nickel crisis 2022, crypto flash crashes). Modern risk engines follow strict multi-tiered default waterfalls to minimize destructive forced liquidations.
  - *Waterfall Staging*:
    - *Stage 1 (Order Deleveraging)*: When an account breaches its maintenance margin requirement ($MMR$), the engine first cancels active resting orders in price-time priority order, releasing locked collateral back to free cash. Crucially, per rule R-W4, the engine must re-evaluate account solvency after each cancellation. If margin release restores solvency, liquidation must cease immediately.
    - *Stage 2 (Backstop Liquidation)*: If the account remains insolvent after all resting orders are cancelled, remaining open positions are transferred to the designated backstop liquidity provider (`LIQ`) at the bankruptcy price.
  - *Conservation Hazards*: Cash debited from the insolvent account must match cash credited to LIQ, ensuring zero leakages from the clearinghouse balance sheet ($I_1$).

---

## 8. Task: f5_basket_b (Family F5, Variant B - Coupled)
- **Target Files**: `exchange_core/handlers/basket.py`
- **Applicable Rules**: R-A1, R-A2, R-A3, R-A4, R-A5
- **Interface**: `handle_basket(engine: Engine, event: Event) -> list[Report]`
- **Difficulty Reason**: Enforces atomic all-or-none multi-leg basket execution across multiple symbols: if any leg rejects, all prior leg fills, margin changes, volume increments, and sequence counters must roll back with zero dangling reports (R-A1 to R-A7).
- **Author Audit**:
  - *Domain Rationale*: Multi-leg basket orders are used in index arbitrage, ETF creation/redemption, and spread trading. Because legs span disparate order books (e.g. Leg 1: BUY AAPL, Leg 2: SELL MSFT), partial executions expose the trader to unhedged directional market risk.
  - *Transactional Rollback Architecture*: Under All-or-None (AON) atomicity, if any leg encounters an error (insufficient depth, price limit rejection, margin exhaustion), the entire transaction must abort.
  - *State Restitution Traps*: In a rollback, restoring only the order book order lists is insufficient. Candidate code must restore:
    1. Account cash balances and locked margin amounts ($I_1, I_2$).
    2. 30-day cumulative volume counters.
    3. Global order ID generators and event sequence counters ($I_3$).
    4. Suppress all intermediate execution reports generated during trial execution so clients receive only a single clean rejection report.

## 9. Task: f6_match_b (Family F6, Variant B - Coupled)
- **Target Files**: `exchange_core/handlers/new_limit.py`
- **Applicable Rules**: R-B4, R-B5, R-M1, R-M2, R-M3, R-M4, R-M5
- **Interface**: `handle_new_limit(engine: Engine, event: Event) -> list[Report]`
- **Difficulty Reason**: see `tasks/f6_match_b/task.toml`.
- **Author Audit**: PENDING. Drafted by the AI assistant; the author has not reviewed this task yet. `author_signoff` stays false until they do.

## 10. Task: f7_funding_b (Family F7, Variant B - Coupled)
- **Target Files**: `exchange_core/handlers/funding.py`
- **Applicable Rules**: R-Y1, R-Y2, R-Y3, R-Y4, R-Y5
- **Interface**: `handle_funding(engine: Engine, event: Event) -> list[Report]`
- **Difficulty Reason**: see `tasks/f7_funding_b/task.toml`.
- **Author Audit**: PENDING. Drafted by the AI assistant; the author has not reviewed this task yet. `author_signoff` stays false until they do.

## 11. Task: f8_adl_b (Family F8, Variant B - Coupled)
- **Target Files**: `exchange_core/handlers/bankruptcy.py`
- **Applicable Rules**: R-L1, R-L2, R-L3, R-L4, R-L5 (R-L0 describes the existing caller)
- **Interface**: `handle_bankruptcy(engine: Engine, account_id: str, pre_position: int) -> list[Report]`
- **Difficulty Reason**: see `tasks/f8_adl_b/task.toml`.
- **Author Audit**: PENDING. Drafted by the AI assistant; the author has not reviewed this task yet. `author_signoff` stays false until they do.

## 12. Tasks: f9_dbg_1 to f9_dbg_6 (Family F9, diagnose and fix)
- **Target Files**: the file of the task each is graded as (`graders` use `grades_as`): `settle.py`, `shock.py`, `basket.py`, `new_limit.py`, `funding.py`, `bankruptcy.py`.
- **Tasks**: `f9_dbg_1` (graded as f1_fee_b), `f9_dbg_2` (f4_waterfall_b), `f9_dbg_3` (f5_basket_b), `f9_dbg_4` (f6_match_b), `f9_dbg_5` (f7_funding_b), `f9_dbg_6` (f8_adl_b).
- **Applicable Rules**: those of the task each is graded as.
- **Interface**: unchanged from the task each is graded as; the model returns the corrected file.
- **Difficulty Reason**: see `tasks/f9_dbg_N/task.toml` and `docs/F9_INSTANCES.md`.
- **Author Audit**: PENDING for all six. Drafted by the AI assistant; the author has not reviewed these tasks yet. `author_signoff` stays false until they do. What to check is in `docs/REVIEW_PACKET.md` section C.
