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
