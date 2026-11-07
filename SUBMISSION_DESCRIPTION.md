# OrderBook-DST: Hackathon Submission Description

### Domain
Mission-critical electronic financial exchange matching and clearing state machines (fixed-point integer accounting, order books, risk ledgers, FIX protocol sequencing).

### What Limitation It Tests
Whether models can implement exchange state-machine components that stay correct
across long, pseudo-random event sequences, not just on the visible unit tests:
cash and margin conservation, price-time priority on replace, FIX sequence-gap
handling, liquidation waterfalls and atomic basket rollback.

### Tasks & Evaluation Architecture
- **17 Tasks across 9 Mechanism Families** (11 implementation tasks in F1–F8, 6 diagnose-and-fix tasks in F9):
  - `F1`: Fee ladders with piecewise rate interpolation, bankers' rounding, and fee vault conservation.
  - `F2`: Order cancel/replace with asymmetric price-time priority retention and locked margin adjustments.
  - `F3`: FIX protocol session sequencing, out-of-order gap buffering, and reset epochs.
  - `F4`: Price shock margin liquidation waterfalls with solvency rechecks.
  - `F5`: Multi-leg atomic basket orders with complete state restitution on rollback.
  - `F6`: The whole order-matching handler: validation order, price-time matching, self-trade prevention mid-sweep, IOC remainder, fee settlement.
  - `F7`: Funding payments between longs and shorts with clamped rates, per-account rounding and fee-vault residual, followed by a mandatory waterfall.
  - `F8`: Bankruptcy after liquidation: capped insurance draw from the fee vault, then pro-rata loss sharing with deterministic leftover distribution, exact money conservation.
  - `F9`: Diagnose and fix. The model gets the specification, a handler with one defect and the first failing step of a short trace, and must return the corrected file. Graded by the grader of the task it is graded as. Exploratory, reported separately from H1–H5.
- **3-Tier Code Grader**:
  - Tier 1: Visible unit tests.
  - Tier 2: 87 targeted edge checkpoints.
  - Tier 3: 20 pseudo-random hidden event traces (200 events each) asserting 4 physical conservation laws ($I_1$ Cash Conservation, $I_2$ Margin Lock Conservation, $I_3$ Order ID Monotonicity, $I_4$ Message Deduplication).
- **Grader Reliability** (`make validate`):
  - The reference and a clean-room second reference both score 1.0 on all 11 implementation tasks. For each F9 task the reference, the clean-room alternative and a minimal hand-written fix score 1.0, and the buggy file scores below 1.0 exactly like its source mutant.
  - All 81 hand-written bug mutants fail with the predicted invariant; empty and hard-coded stubs score near 0; grading is deterministic.
  - Of the 81 bugs, 54 fail a visible test, 21 more are caught first by a checkpoint, and 6 (for example `m_lock_uses_current_rate`, see `make demo`) pass every visible test and checkpoint and are caught only by the hidden simulation.

### Models Evaluated & Headline Results
Seven free-tier models, 3 trials per task, 329 real trials (see the README for exact model IDs, settings and run dates). Pass rate on the 11 implementation tasks: nemotron_ultra 100%, mistral_large 93.9%, gemini_35_flash 87.5% (incomplete: free-tier rate limits), gemma_26b 81.8%, flash_lite 78.8%, nemotron_nano 36.4%, ministral_8b 36.4%. The visible tests overstate quality for weaker models (ministral_8b loses 0.50 of score between the visible tests and the hidden simulations), and invariant feedback repairs failures (gemma_26b 60% to 100%, flash_lite 60% to 93%). The strongest models pass nearly everything, so the benchmark separates small and mid models and not the top.

### Human Review
A blinded audit of 20 trials: reading code missed 9 of the 10 failures the hidden simulations caught (kappa 0.10), and the grader was right in every disagreement checked. Task sign-offs and hand-checked examples are in `EXPERT_REVIEW.md`.
