# HYPOTHESES

Pre-registration of hypotheses and predicted failure modes before model evaluation runs.
See `docs/04_RULEBOOK.md` and `docs/05_INVARIANTS_AND_DATA.md`.

## 1. Pre-Registered Hypotheses

### H1: Tier 1 vs Tier 3 Score Gap (Generalization Deficit)
- **Statement**: For each evaluated model, the visible unit test score (Tier 1) will be strictly higher than the hidden multi-event trace simulation score (Tier 3).
- **Metric**: Difference $\Delta_{1-3} = \text{Mean}(T_1) - \text{Mean}(T_3)$ computed across all 10 tasks and trials.
- **Expected Direction**: Positive gap ($\Delta_{1-3} > 0$). Models will fit the static test examples visible in the prompt but fail to generalize to dynamic state trajectories spanning hundreds of sequential transitions.
- **Rejection Condition**: A model achieves $T_3 \ge T_1$ across tasks, or the 95% bootstrap confidence interval of $(T_1 - T_3)$ contains 0 or negative values.

### H2: Variant Coupling Penalty (Isolated vs Coupled State)
- **Statement**: Within each task family, candidate models will exhibit a statistically significant performance drop on Variant B (multi-subsystem coupled state handler) compared to Variant A (isolated domain rule function).
- **Metric**: Coupling Penalty $\Delta_{\text{coupling}} = \text{Score}(\text{Variant A}) - \text{Score}(\text{Variant B})$ paired across task families (F1, F2, F3).
- **Expected Direction**: Positive penalty ($\Delta_{\text{coupling}} > 0$). Models will correctly implement the core transformation logic but consistently omit or corrupt secondary subsystem state (e.g. fee vaults, priority queues, session sequence epochs, margin locks).
- **Rejection Condition**: Mean score of Variant B is equal to or higher than Variant A ($\Delta_{\text{coupling}} \le 0$).

### H3: Invariant Feedback Loop Benefit
- **Statement**: Providing models with targeted invariant violation feedback (invariant ID, plain name, and failure explanation) enables significant error correction over successive turns without leaking test inputs.
- **Metric**: Multi-turn gain $\Delta_{\text{feedback}} = \text{Score}(\text{Turn } n) - \text{Score}(\text{Turn } 1)$ for $n \in \{2, 3\}$.
- **Expected Direction**: Positive gain ($\Delta_{\text{feedback}} > 0$). Invariant feedback provides orthogonal debugging signal that allows reasoning models to identify hidden conservation law breaches.
- **Rejection Condition**: Mean score does not improve or decreases on Turn 2 ($\Delta_{\text{feedback}} \le 0$).

### H4: Frontier Capability Scaling on Conservation Invariants
- **Statement**: Frontier models will achieve significantly higher survival rates against conservation invariants ($I_1$ Cash Conservation, $I_2$ Margin Lock Conservation) than smaller or open-weights models.
- **Metric**: Invariant pass rate $P(I_k) = \frac{\text{Passed Traces without } I_k \text{ violation}}{\text{Total Evaluated Traces}}$.
- **Expected Direction**: $P(I_k \mid \text{Frontier}) > P(I_k \mid \text{Smaller})$.
- **Rejection Condition**: A smaller model achieves equivalent or higher conservation invariant pass rate than a frontier model.

### H5: Secondary Component Omission Attribution
- **Statement**: In Variant B coupled tasks, the vast majority of Tier 3 first-failure events will stem from secondary state omissions (e.g. failing to debit the fee vault, omitting priority counter increments, or skipping lock releases) rather than incorrect primary calculation.
- **Metric**: Proportion of first-failure invariant violations classified as Secondary Component Omission versus Primary Logic Error.
- **Expected Direction**: Secondary Component Omissions account for $\ge 60\%$ of all first-failure events on Variant B tasks.
- **Rejection Condition**: Primary logic errors account for $> 40\%$ of Variant B failures.

---

## 2. Expected Failure Types by Family

### Family F1 (Fee Schedule & Vault Settlement)
- **Piecewise Tier Boundary Crossing**: Models will apply a single tier rate to an entire fill that crosses a 30-day volume tier boundary, rather than splitting the fill proportionally across tiers per R-F2.
- **Round-Half-Even vs Round-Half-Up**: Models will use standard mathematical rounding ($0.5 \to 1$) or floating-point division rather than integer-exact IEEE 754 round-half-even (bankers' rounding), failing exact checkpoint tolerances on tie boundaries per R-F1/R-F4.
- **Premature Volume Accumulation**: In F1B, models will update the trader's 30-day cumulative volume prior to computing the taker fee for the current fill, prematurely triggering a tier discount per R-B5.
- **Vault Conservation Breach**: In F1B, models will pay maker rebates directly from system cash rather than debiting the exchange fee vault, violating Cash Conservation ($I_1$).

### Family F2 (In-Flight Replace & Priority Retention)
- **Partial Fill Underflow**: Models will fail to validate `new_qty > cum_qty` on partially filled orders, accepting replacements that reduce the order below its already-filled quantity per R-P2.
- **Priority Timestamp Reset on Reduction**: Models will unconditionally update the order's priority timestamp on any replacement, incorrectly penalizing downward size revisions that are entitled to maintain priority per R-P1.
- **Stale Margin Rate Application**: In F2B, models will compute new margin requirements using the current engine default margin rate instead of preserving the order's original locked margin rate per R-P4.
- **Queue Desynchronization**: In F2B, models will update order fields in `OrderState` but forget to synchronize the underlying price level queue in the `OrderBook`.

### Family F3 (FIX Session Sequencing & Gap Filling)
- **Immediate Execution of Out-of-Order Messages**: Models will execute sequence gap messages immediately rather than queuing them in the session buffer awaiting ResendRequest processing per R-S2.
- **Non-Ascending Buffer Drain**: When a missing sequence arrives, models will drain the buffered queue in arbitrary or FIFO arrival order rather than strict sequence number order per R-S4.
- **PossDupFlag Misinterpretation**: Models will allow `PossDupFlag(43)=Y` to bypass sequence gap detection or execute duplicate messages without checking against `next_in_seq` per R-S5.
- **Epoch Desynchronization**: In F3B, models will execute session reset without incrementing the session epoch or without clearing pending message buffers, triggering duplicate event dispatches ($I_4$).

### Family F4 (Price Shock Waterfall & Liquidation)
- **Inverted Waterfall Execution**: Models will initiate Stage 2 liquidation against the designated liquidity account (LIQ) before cancelling active resting orders in Stage 1 per R-W1/R-W2.
- **Premature Liquidation**: Models will fail to re-evaluate account solvency after Stage 1 order cancellations release locked margin, unnecessarily liquidating accounts that have recovered solvency per R-W4.
- **Priority Violation in Account Ordering**: Models will liquidate underwater accounts in arbitrary order rather than strictly sorting by lowest margin ratio ascending per R-W3.
- **Unbalanced Liquidation Bookings**: Models will transfer positions to LIQ at bankruptcy price without balancing cash adjustments, violating Cash Conservation ($I_1$).

### Family F5 (Atomic Multi-Leg Basket Execution & Rollback)
- **Partial Fill Leakage on Abort**: When an intermediate leg of a multi-leg basket order fails liquidity or margin checks, models will fail to roll back previously executed legs, violating All-or-None atomicity per R-A1.
- **Incomplete State Rollback**: On basket rejection, models will revert the order book state but fail to restore account balances, cumulative volume counters, or global order sequence counters per R-A5.
- **Dangling Fill Reports**: Models will emit execution reports for intermediate fills that are subsequently aborted, corrupting client downstream event logs per R-A4.

---

## Amendment A1 (2026-11-04, before any real model run): analysis methods

The predictions above are unchanged. These notes fix how each one is computed,
written before any real model output existed:

- **H1**: T1 − T3 is taken per trial (both tiers grade the same code), averaged per
  task, with a hierarchical bootstrap CI. Trials that never reached tier 3
  (format, import, tier 1/2 errors) are excluded, because their T3 of 0 is a
  placeholder.
- **H2**: the original text said "paired across task families". Trials on task A
  and task B are independent calls on different tasks, so they cannot be paired
  trial-by-trial. The test is instead a one-sided permutation test that shuffles
  A/B labels within each family (F1–F3), on both pass rate and mean score.
  Variant B tasks are also longer than A tasks; a positive result is reported as
  "B is harder than A", not as a pure coupling effect.
- **H3**: paired by trial (turn 0 vs final turn of the same trial), exact McNemar
  test on pass/fail, plus mean score gain.
- **H4**: per-invariant survival = share of evaluated hidden seeds on which that
  invariant was never violated.
- **H5**: the grader compares reports (D1) before checking invariants, so a
  conservation breach that also changes a report would be labelled D1. For H5 the
  grader records every invariant broken at each failing seed's first failing
  event. "Secondary omission" is proxied by "a conservation invariant (I1–I4)
  broke"; "primary logic error" by "report or final state differs with no
  invariant broken". The proxy is checked against the transcripts by hand.
- **Grader-level prior** (no model involved): of the 35 hand-written mutants, 32
  already fail a visible test, 2 are caught first by checkpoints and 1 only by the
  hidden traces (`results/grader_analysis/mutant_tiers.md`). If model bugs resemble
  these mutants, H1's gap will be small; a large gap would mean models make a
  different kind of mistake than the author anticipated.

---

## Amendment A2 (2026-11-04, written after the first pilot runs; recorded so the change is visible)

A1 above was written before any model run. The first pilot runs found grader and task problems that were fixed before any result counts. None changes a prediction or how a hypothesis is computed:

- Coupled-task instructions now document `engine.cfg`, `engine.state` and `engine.dispatch`; before, a model could not know the attribute names (it failed for a reason the prompt never covered).
- The output-format instructions contradicted the system message and the extractor accepted only one layout; both layouts are now accepted and the instructions agree.
- The hidden simulation now also compares the whole final engine state with the reference's. A model skipped a required state update (storing the mark price) and still scored T3 = 1.00. The grader-level prior therefore changes: of **36** hand-written mutants (one added for this gap), 33 fail a visible test, 2 are caught first by checkpoints and 1 only by the hidden traces.
- Trials that end because the model ran out of output tokens are reported as `OUTPUT_TRUNCATED`, separate from format errors.
- Pilot results from before these fixes are discarded and not used anywhere.

---

## 3. Post-Run Analysis: What Was Wrong in My Predictions

*(To be written by the author after the real model runs, from the transcripts in
`results/main/raw/`.)*

Note: an earlier version of this section reported "CONFIRMED" verdicts based on
simulated results that did not come from any model. That analysis has been
withdrawn; see `AI_USE.md`.
