# Human Grader Audit Report

## 1. Summary of Agreement

- **Total Sampled Trials**: 20
- **Cohen's Kappa (κ)**: 0.9000

### 2x2 Contingency Matrix

| | Human PASS (Correct) | Human FAIL (Incorrect) | Total |
|---|:---:|:---:|:---:|
| **Grader PASS** | 10 (TP) | 0 (FP) | 10 |
| **Grader FAIL** | 1 (FN) | 9 (TN) | 10 |
| **Total** | 11 | 9 | 20 |

## 2. Disagreements and Diagnostics

### Disagreement 1: Task `f5_basket_b` (Model: flash_lite, Trial: 2)
- **Grader Verdict**: FAIL
- **Human Verdict**: PASS
- **Author Reason**: Implements R-A1 through R-A5 correctly - IOC fully filled returns None from get_order (passes check), IOC partial fill caught by CANCELLED report or order.leaves > 0 check


## 3. Audited Trials Detail

| Trial # | Task ID | Model | Grader Verdict | Human Verdict | Author Reason |
|:---:|---|---|:---:|:---:|---|
| 1 | `f4_waterfall_b` | `ministral_8b` | FAIL | FAIL | Uses engine.accounts and engine.mark_price which do not exist on Engine (only engine.state); passes engine instead of state to get_account_orders and remove_order, causing crashes |
| 2 | `f4_waterfall_b` | `mistral_large` | PASS | PASS | Implements R-W1 through R-W5 correctly with proper Stage 1 recheck (R-W4) - sets mark price, checks breach, cancels orders in priority order, rechecks breach, and liquidates if still breached |
| 3 | `f3_fix_b` | `nemotron_ultra` | PASS | PASS | Implements R-S1 through R-S5 and R-S8 for FIX session handling - session creation, epoch check, sequence validation with duplicate detection, buffer management, and session reset |
| 4 | `f5_basket_b` | `gemma_26b` | FAIL | FAIL | IOC fully filled: order removed from state.orders, get_order returns None, 'not order' incorrectly marks as failed; a fully-filled IOC should succeed |
| 5 | `f5_basket_b` | `flash_lite` | FAIL | PASS | Implements R-A1 through R-A5 correctly - IOC fully filled returns None from get_order (passes check), IOC partial fill caught by CANCELLED report or order.leaves > 0 check |
| 6 | `f1_fee_b` | `nemotron_ultra` | PASS | PASS | Implements R-M4, R-F1, R-F2, R-F3 correctly - proper cash/position updates, tiered fee computation based on pre-fill volume, rebate, vault update, and volume recording |
| 7 | `f6_match_b` | `ministral_8b` | FAIL | FAIL | Order created with type('Order', (), {...}) without 'leaves' attribute; order.leaves on line 627 crashes with AttributeError on first fill attempt |
| 8 | `f6_match_b` | `ministral_8b` | FAIL | FAIL | Bids for SELL orders sorted ascending causes matching loop to break on first bid below sell limit, violating R-M1/R-M2 price-time priority for SELL side |
| 9 | `f5_basket_b` | `nemotron_nano` | FAIL | FAIL | Checks leg_reports[0].kind == 'BASKET_ROLLED_BACK' but NEW_LIMIT dispatch never returns BASKET_ROLLED_BACK; failed legs (REJECTED, partial IOC) are never detected |
| 10 | `f2_replace_a` | `nemotron_ultra` | PASS | PASS | Implements R-P1 through R-P3 correctly - proper price validation, quantity check against cum_qty, and priority retention (same price AND new_qty <= old qty) |
| 11 | `f6_match_b` | `gemma_26b` | PASS | PASS | Implements R-B4 through R-B5 and R-M1 through R-M5 correctly - proper validation, margin locking, iterative matching with STP, lock updates per fill, and IOC/rest handling |
| 12 | `f4_waterfall_b` | `gemma_26b` | PASS | PASS | Implements R-W1 through R-W5 correctly - mark price setting, breach check, Stage 1 cancellation with lock release, R-W4 recheck, and Stage 2 liquidation only if still breached |
| 13 | `f1_fee_a` | `mistral_large` | PASS | PASS | Implements R-F2 and R-F3 correctly - tiered taker fee based on pre-fill volume, and maker rebate per-notional rate using round_half_even |
| 14 | `f1_fee_b` | `mistral_large` | PASS | PASS | Implements R-M4, R-F1, R-F2, R-F3 correctly - proper cash/position updates, tiered fee computation, rebate, vault update, and FILL report |
| 15 | `f5_basket_b` | `ministral_8b` | FAIL | FAIL | IOC partial fill with cancelled remainder: order removed from state.orders, get_order returns None, 'if order and order.leaves != 0' passes incorrectly; should fail because IOC was not fully filled |
| 16 | `f3_fix_a` | `flash_lite` | PASS | PASS | Implements R-S1 through R-S5 correctly - epoch check, sequence validation with duplicate detection, and buffer management for out-of-order messages |
| 17 | `f4_waterfall_b` | `gemini_35_flash` | PASS | PASS | Implements R-W1 through R-W5 correctly - mark price, breach check, Stage 1 cancellation with lock release, R-W4 recheck, and Stage 2 liquidation only if still breached |
| 18 | `f2_replace_b` | `ministral_8b` | FAIL | FAIL | engine.book does not exist on Engine (only engine.state); crossing check also uses wrong book side (BUY checks best_bid instead of best_ask) |
| 19 | `f4_waterfall_b` | `ministral_8b` | FAIL | FAIL | free_cash captured before Stage 1 cancellation; release_lock updates account.free_cash but R-W4 recheck at line 1703 uses stale free_cash value |
| 20 | `f1_fee_b` | `nemotron_nano` | FAIL | FAIL | pay_fee, pay_rebate, adjust_position, add_volume are module-level ledger functions, not EngineState methods; state.pay_fee() etc. crash with AttributeError |
