# OrderBook-DST: Hackathon Submission Description

### Domain
Mission-critical electronic financial exchange matching and clearing state machines (fixed-point integer accounting, order books, risk ledgers, FIX protocol sequencing).

### What Limitation It Tests
Whether models can implement exchange state-machine components that stay correct
across long, pseudo-random event sequences, not just on the visible unit tests:
cash and margin conservation, price-time priority on replace, FIX sequence-gap
handling, liquidation waterfalls and atomic basket rollback.

### Tasks & Evaluation Architecture
- **8 Tasks across 5 Mechanism Families**:
  - `F1`: Fee ladders with piecewise rate interpolation, bankers' rounding, and fee vault conservation.
  - `F2`: Order cancel/replace with asymmetric price-time priority retention and locked margin adjustments.
  - `F3`: FIX protocol session sequencing, out-of-order gap buffering, and reset epochs.
  - `F4`: Price shock margin liquidation waterfalls with solvency rechecks.
  - `F5`: Multi-leg atomic basket orders with complete state restitution on rollback.
- **3-Tier Code Grader**:
  - Tier 1: Visible unit tests.
  - Tier 2: 73 targeted edge checkpoints.
  - Tier 3: 20 pseudo-random hidden event traces (200 events each) asserting 4 physical conservation laws ($I_1$ Cash Conservation, $I_2$ Margin Lock Conservation, $I_3$ Order ID Monotonicity, $I_4$ Message Deduplication).
- **Grader Reliability** (`make validate`):
  - The reference and a clean-room second reference both score 1.0 on all 9 tasks.
  - All 46 hand-written bug mutants fail with the predicted invariant; empty and hard-coded stubs score near 0; grading is deterministic.
  - 33 of the 36 bugs already fail a visible test; one (`m_lock_uses_current_rate`) passes every visible test and checkpoint and is caught only by the hidden simulation (`make demo`).

### Models Evaluated & Headline Results
*(To be filled in from the real model runs in `results/main/`. No model results
are claimed yet.)*
