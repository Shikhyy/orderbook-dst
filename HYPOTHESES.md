# HYPOTHESES

Pre-registration of hypotheses and predicted failure modes before any model evaluation run.
See `docs/01_CHARTER.md` section 3 and `docs/12_RESEARCH_PLAN.md` section 1.

## 1. Pre-Registered Hypotheses

### H1: Tier 1 vs Tier 3 Score Gap
- **Statement**: For each model, the Tier 1 score is higher than the Tier 3 score.
- **Metric**: Mean Tier 1 score minus mean Tier 3 score across all tasks and trials.
- **Expected Direction**: Positive gap (T1 > T3).
- **Rejection Condition**: A model achieves T3 >= T1 across tasks, or the 95% bootstrap confidence interval of (T1 - T3) includes 0 or negative values.

### H2: Variant Coupling Penalty (Isolated vs Coupled)
- **Statement**: For each model, variant B (coupled state) has a lower pass rate than variant A (isolated function), paired by task family.
- **Metric**: Pass rate of Variant A minus pass rate of Variant B.
- **Expected Direction**: Positive gap (Pass(A) > Pass(B)).
- **Rejection Condition**: Mean pass rate of Variant B is equal to or greater than Variant A.

### H3: Invariant Feedback Loop Benefit
- **Statement**: When the model sees the invariant report in multi-turn feedback, the pass rate increases.
- **Metric**: Turn 2 pass rate minus Turn 1 pass rate in feedback mode.
- **Expected Direction**: Positive delta (Turn 2 > Turn 1).
- **Rejection Condition**: Pass rate does not improve or decreases on Turn 2.

### H4: Capability Scaling
- **Statement**: A stronger frontier model has a higher pass rate than a smaller or older model.
- **Metric**: Overall pass@1 and pass^5 rank ordering among evaluated models.
- **Expected Direction**: Monotonically increasing pass rate with benchmark capability tier.
- **Rejection Condition**: A smaller model strictly outperforms a frontier model on pass@1.

### H5: Secondary Component Failure Attribution
- **Statement**: Most Tier 3 failures at variant B come from state that the candidate code does not update in a second component (e.g. fee vault, order book prio, margin locks).
- **Metric**: Proportion of first-failure invariants attributed to secondary state updates versus primary logic.
- **Expected Direction**: Majority (>50%) of failure traces show secondary component desynchronization.
- **Rejection Condition**: Direct primary return/logic errors account for >= 50% of Tier 3 failures.

## 2. Expected Failure Types by Family

- **Family F1 (Fee schedule and fee vault settlement)**: AUTHOR TO WRITE
- **Family F2 (Replace order in-flight and priority update)**: AUTHOR TO WRITE
- **Family F3 (FIX session message sequence and gap filling)**: AUTHOR TO WRITE
- **Family F4 (Price shock waterfall and liquidation against LIQ)**: AUTHOR TO WRITE
- **Family F5 (Atomic multi-leg basket order execution and rollback)**: AUTHOR TO WRITE

## 3. Post-Run Analysis: What Was Wrong in My Predictions

*(To be authored and committed after model experimental runs conclude)*
