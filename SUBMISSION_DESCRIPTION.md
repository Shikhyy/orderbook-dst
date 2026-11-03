# OrderBook-DST: Hackathon Submission Description

### Domain
Mission-critical electronic financial exchange matching and clearing state machines (fixed-point integer accounting, order books, risk ledgers, FIX protocol sequencing).

### What Limitation It Reveals
1. **The Generalization Deficit**: LLMs easily satisfy prompt-visible unit tests (Tier 1 scores: 81%–89%), but collapse on long-horizon dynamic state trajectories spanning hundreds of sequential transitions (Tier 3 scores: 20%–60%).
2. **The Component Coupling Penalty**: LLMs suffer from severe architectural "tunnel vision." Across all evaluated models, performance drops precipitously when moving from isolated pure functions (Variant A: 80%–93% pass rate) to coupled multi-subsystem handlers (Variant B: 12%–32% pass rate; McNemar test $p < 0.05$). Over 72.9% of failures on coupled tasks are caused by secondary state omissions (e.g. failing to debit exchange fee vaults, skipping margin lock adjustments, or omitting sequence counter increments) while the primary transformation logic appears completely correct.

### Tasks & Evaluation Architecture
- **8 Tasks across 5 Mechanism Families**:
  - `F1`: Fee ladders with piecewise rate interpolation, bankers' rounding, and fee vault conservation.
  - `F2`: Order cancel/replace with asymmetric price-time priority retention and locked margin adjustments.
  - `F3`: FIX protocol session sequencing, out-of-order gap buffering, and reset epochs.
  - `F4`: Price shock margin liquidation waterfalls with solvency rechecks.
  - `F5`: Multi-leg atomic basket orders with complete state restitution on rollback.
- **Rigorous 3-Tier Grader**:
  - Tier 1: Visible unit tests.
  - Tier 2: 59 targeted edge checkpoints.
  - Tier 3: 20 pseudo-random hidden event traces (200 events each) asserting 4 physical conservation laws ($I_1$ Cash Conservation, $I_2$ Margin Lock Conservation, $I_3$ Order ID Monotonicity, $I_4$ Message Deduplication).
- **Grader Reliability**:
  - 100% kill rate on 35 hand-crafted fault mutants.
  - Dual clean-room reference solutions (`reference/` and `reference_alt_v2/`) independently scoring 1.0000 across 272,000 events and 544,000 invariant checks.

### Models Evaluated & Headline Results
- **Claude 3.5 Sonnet (`20241022`)**: 55.0% Pass Rate (Mean Score 0.713, pass@5: 100%, pass^5: 25.0%).
- **GPT-4o (`2024-08-06`)**: 37.5% Pass Rate (Mean Score 0.619, pass@5: 75.0%, pass^5: 0.0%).
- **Qwen 2.5 Coder 7B (`Instruct`)**: 10.0% Pass Rate (Mean Score 0.439, pass@5: 37.5%, pass^5: 0.0%).

### The Hot Take: Invariant Feedback Loops
Unit tests reinforce model tunnel vision. Supplying models with structured invariant violation reports (`[Invariant ID, Plain Name, Message]`) without leaking test inputs unlocks dramatic self-repair capabilities: Claude 3.5 Sonnet's pass rate jumped from **0.0% on initial failure to 60.0% on Turn 1 (+60% revision gain)**.
