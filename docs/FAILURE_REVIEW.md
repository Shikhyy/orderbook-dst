# Failure review (working notes)

Each failing trial is read against the reference and the task text, to decide
whether the model or the task/grader is at fault. Written during the run; the
author confirms each verdict before it is used in the write-up.

| trial | score | cause | verdict |
|---|---|---|---|
| mistral_large, f2_replace_a, trial 0 | 0.68 | Same price and same quantity: model gives the order a new `prio_seq` (`keep_priority = new_qty < order.qty`). Spec R-P3 says "nothing changes" for equal qty, so priority must be kept. Visible tests pass; 12 of 20 hidden seeds fail (D1_STATE at the final state, one D1 report mismatch). | Model fault. The spec states the case explicitly. Good example of H1: passes visible tests, fails hidden traces on an edge case. |
