# Failure review (working notes)

Each failing trial is read against the reference and the task text, to decide
whether the model or the task/grader is at fault. Written during the run; the
author confirms each verdict before it is used in the write-up.

| trial | score | cause | verdict |
|---|---|---|---|
| mistral_large, f2_replace_a, trial 0 | 0.68 | Same price and same quantity: model gives the order a new `prio_seq` (`keep_priority = new_qty < order.qty`). Spec R-P3 says "nothing changes" for equal qty, so priority must be kept. Visible tests pass; 12 of 20 hidden seeds fail (D1_STATE at the final state, one D1 report mismatch). | Model fault. The spec states the case explicitly. Good example of H1: passes visible tests, fails hidden traces on an edge case. |

## Task defect found during review

| issue | evidence | fix |
|---|---|---|
| F3 spec said a FIX session's `epoch` and `next_seq` "both start at 1" and never said sessions are created on first use. The reference creates them lazily with `epoch=0`. | f3_fix_b: 5 trials from gemma_26b, ministral_8b and nemotron_nano crashed with `KeyError: 'S1'` at event 0, and any model that guessed epoch 1 would mismatch. | Instructions for f3_fix_a and f3_fix_b now state `epoch` starts at 0 and lazy creation with `SessionState(epoch=0, next_seq=1, buffer={})`. All earlier f3_fix_b trials were discarded and re-run. |

## Reviewed and judged model faults

- gemma_26b, f1_fee_b (3 trials): indexes `state.accounts` by an order id; its own comment says "This is wrong". The `Fill` schema is documented.

## Output-token budget

- mistral_large had `max_tokens = 8000`, lower than the 16000 given to the other reasoning models. One trial (f4_waterfall_b) ended with no visible answer after using the whole budget. The limit was raised to 16000 and that trial re-run: score 1.00. The other 23 mistral_large trials ran at 8000 and finished normally.
- nemotron_nano (16000 tokens) ran out of tokens on f1_fee_b and f3_fix_a. Same budget as its peers, so these stay recorded as `OUTPUT_TRUNCATED` model behaviour (the model reasons without finishing).

## f6_match_b

| trial | score | cause | verdict |
|---|---|---|---|
| gemma_26b, trial 1 (second trial) | 0.23 | Matching loop picks the best opposite order with `for ask in asks: if ask.price <= order.price: best_opp = ask else: break`, with no `break` after the assignment. It keeps overwriting, so it ends on the **last** crossing order (worst price) instead of the first. Passes all 8 visible tests (each has one crossing order); fails 11 of 12 checkpoints and all 20 hidden seeds at the first multi-level sweep. | Model fault. R-M1 says "matches the best price first". Clean example of H1: the visible tests never put two crossing orders in the book. |
| mistral_large, trial 1 | 0.00 | `OUTPUT_TRUNCATED` at 16000 tokens on this larger task. | Not scored as wrong code. Token budget to be reviewed for F6 once all models have run. |

### f6_match_b, remaining trials (all read against the reference and the task text)

| trial | score | cause | verdict |
|---|---|---|---|
| gemma_26b, trial 2 | 0.50 | Passes visible tests and all 12 checkpoints; fails hidden seeds with I3 "order has leaves 0": a completely filled incoming order ends up stored in `state.orders`. | Model fault. The task says "An order that is completely filled is never stored in `state.orders`". |
| ministral_8b, trial 0 and 2 | 0.05, 0.08 | Crashes at event 0/3 (`type object 'Order' has no attribute 'leaves'`): treats `leaves` as a writable field. `types.py` documents it as a derived property. | Model fault. |
| ministral_8b, trial 1 | 0.15 | Sorts the opposite side ascending by price for both sides, so a SELL matches the lowest bid first (R-M1: best price first); self-trade prevention only implemented for BUY orders (R-M3 applies to both sides). | Model fault. |

F6 summary: flash_lite 3/3 pass, mistral_large 2/3 (+1 truncated), gemma_26b 1/3, ministral_8b 0/3. gemini_35_flash and the two nemotron models have no F6 trials yet (rate limits).

## f7_funding_b

| issue | evidence | verdict / fix |
|---|---|---|
| **Task defect I introduced.** After the clean-room agent asked whether an account with `amount == 0` counts, I reworded R-Y4 to "`n` is ... every account with `position != 0`, even when its `amount` is 0 (`n = 0` when `rate == 0`)". The first half reads as unconditional and clashes with the parenthetical. | 4 of the first 5 failing F7 trials (gemma_26b trial 1, flash_lite trials 0 and 2, ministral_8b trial 0) report `qty = n > 0` for a zero rate and fail only the hidden seeds that contain zero-rate funding events (D1 at event 53). | Task defect, not model fault. R-Y4 now says: if `rate == 0` no account is processed and `n = 0`; if `rate != 0`, `n` counts every account with a position, including one whose amount rounds to 0. All F7 trials run on the old wording were discarded (12 trials) and re-run. |
| ministral_8b, trials 0 and 1 (also) | I1 "total money != initial" on every hidden seed: the net rounding difference is never added to `fee_vault` (R-Y3). | Model fault. R-Y3 states it explicitly. |

Lesson for the write-up: a clean-room read finds ambiguities, but the fix itself needs to be re-read cold. The first F7 results were a useful catch of my own wording error.

### f7_funding_b, results on the corrected wording

| model | trials | scores |
|---|---|---|
| mistral_large | 3 | 1.00, 1.00, 1.00 |
| gemma_26b | 3 | 1.00, 1.00, 1.00 |
| flash_lite | 3 | 1.00, 1.00, 1.00 |
| ministral_8b | 3 | 0.20, 0.20, 0.20 |
| gemini_35_flash, nemotron_ultra, nemotron_nano | 0 | not run yet (rate limits / daily cap) |

ministral_8b fails all three with I1 ("total money != initial", off by 1 or 2 micro-units): it never books the net per-account rounding difference into `fee_vault` correctly (R-Y3 states it; two trials do not touch `fee_vault`, one does it wrongly). It passes all visible tests and gets 0 of 6 checkpoints, so it also misses the exact-tie and residual checkpoints. Model fault.

Reading: on F7 the three stronger models are at 1.00 once the spec wording was fixed. F7 separates only the weakest model, so it adds little headroom at the top; its value is as a clean, well-specified coupled task where a failure is attributable.

## Main run: remaining failures (Nov 5, nemotron_nano complete, gemini_35_flash in progress)

### nemotron_nano (30/30 trials, 10 passed, mean 0.408)
Spec/harness defects: none found. Failures group as follows.

| category | count | tasks | verdict |
|---|---|---|---|
| OUTPUT_TRUNCATED at the shared max_tokens budget | 10 | f1_fee_b, f3_fix_a, f4_waterfall_b x2, f5_basket_b, f6_match_b x3, f7_funding_b x2 | Budget artifact, not a logic finding. Every model has the same budget. Report separately from logic failures. |
| Tier 2 crash on invented attributes (Engine.orders / .accounts / .book / .release_lock, EngineState.adjust_position) | 5 | f1_fee_b x2, f2_replace_b x3 | Genuine model limitation: calls APIs that are not in the provided code. |
| Wrong behaviour in the hidden traces (D1 report mismatch or I1 money conservation) | 5 | f3_fix_b t1 (0.38), f5_basket_b t0 (0.10) and t2 (0.39), f7_funding_b t0 (0.20), f3_fix_b t0 (0.98 near miss) | Logic failures. NOT YET READ in detail, so no root cause is claimed. f3_fix_b t0 at 0.98 needs a check for a spec gap. |

### gemini_35_flash f5_basket_b (3/3 at 0.50)
The handler treats any CANCELLED report as a failed leg. Rule R-A3 fails the basket only on a rejection or an IOC remainder, so a self-trade-prevention cancel must not fail it. This is a model misreading, consistent across trials. No spec defect identified.

### Spec defect: f3_fix_b body=None (found Nov 5)
nemotron_nano f3_fix_b t0 scored 0.98: it failed one public test (test_epoch_mismatch) because it dispatched a message with `body=None`. The reference skips dispatch for a None body and 7 public tests rely on it, but the instruction never said so. This is a spec gap, not a model failure. R-S9 now states the rule. All f3_fix_b trials must be rerun on the corrected wording, as was done for the earlier F3 epoch defect.

### nemotron_nano logic failures, read (Nov 5)
- f5_basket_b t0 (0.10) and t2 (0.39): when a leg is rejected (e.g. POST_ONLY_WOULD_CROSS) or leaves an IOC remainder, the model emits the per-leg ACCEPTED/REJECTED/CANCELLED reports instead of rolling the whole basket back with BASKET_ROLLED_BACK. It does not implement all-or-nothing atomicity. Genuine model limitation; the spec states the rollback rule.
- f7_funding_b t0 (0.20): total money is 2 units below the initial total at event 34 (I1). Funding amounts are rounded so that the residual is not fully credited to the fee vault. Genuine rounding/conservation bug, caught by the conservation invariant.
- f3_fix_b t1 (0.38): first report has order_id 0 instead of 1 (ids start at 1). It will be re-judged on the corrected rerun.
