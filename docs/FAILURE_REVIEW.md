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
