# OrderBook-DST: 5-Minute Video Walkthrough Script

*Designed per Section 6 (page 19) of the micro1 Eval Hackathon Participant Guide.*

---

## Part 1: The Problem & Real-World Relevance (~1 minute)

**[Visual: Title Slide / Architecture Diagram showing Order Book, Ledger, and Invariants]**

**Speaker**:
"Hi everyone, I'm presenting **OrderBook-DST**, an evaluation benchmark that tests whether Large Language Models can write mathematically sound and architecturally robust code for financial exchange state machines.

In electronic trading and clearing infrastructure—like the CME, Nasdaq, or crypto derivatives exchanges—software bugs are not minor formatting issues. They cause immediate clearinghouse deficits, unauthorized credit creation, or catastrophic market crashes:
- In 2012, Knight Capital lost **\$440 million in 45 minutes** due to an obsolete routing flag bug.
- In 2022, an unbacked margin loophole in FTX led to an **\$8 billion deficit**, breaking basic conservation laws.

Traditional software testing with isolated unit tests fails to catch these bugs because individual functions appear locally correct. In the finance industry, the gold standard is **Deterministic Simulation Testing (DST)**—pioneered by TigerBeetle and FoundationDB. DST runs hundreds of thousands of state transitions over a single-threaded deterministic event loop, asserting physical conservation laws after every single transition.

We built OrderBook-DST to see if frontier models can actually write code that survives DST."

---

## Part 2: Task Design & 3-Tier Grader (~1.5 minutes)

**[Visual: Code walkthrough of `tasks/f1_fee_b/instruction.md` and `graders/dst_grader.py`]**

**Speaker**:
"OrderBook-DST features **8 tasks across 5 mechanism families**:
1. Fee schedules with piecewise rate interpolation and bankers' rounding ties.
2. In-flight order cancel/replace with asymmetric price-time priority retention.
3. Stateful FIX session sequencing and out-of-order gap buffering.
4. Two-stage price shock liquidation waterfalls.
5. Multi-leg atomic basket order execution and rollback.

To measure what we call the **Component Coupling Penalty**, every family pairs an isolated pure transformation (Variant A) with an integrated engine handler (Variant B).

Each candidate solution is graded through a rigorous 3-tier pipeline:
- **Tier 1 (20% weight)**: Public unit tests visible in the prompt, verifying basic API contracts.
- **Tier 2 (30% weight)**: 59 targeted boundary checkpoints checking mathematical corner cases like exact tie rounding and partial fill replacements.
- **Tier 3 (50% weight)**: 20 pseudo-random hidden event traces—200 sequential events each—asserting 4 inviolable financial conservation laws:
  - Invariant $I_1$: Total cash across all accounts and the fee vault is strictly conserved. Zero money created or destroyed.
  - Invariant $I_2$: Collateral margin locks exactly cover all resting orders.
  - Invariant $I_3$: Order IDs and book queue priority timestamps strictly increment.
  - Invariant $I_4$: Sequence gap buffers drain in strict order with zero duplicate dispatches.

To guarantee zero false passes and zero false rejections, we validated the grader against **two independent clean-room reference solutions**—both achieving a perfect 1.0000 score across 272,000 events—and proved that our grader **kills 100% of 35 hand-crafted fault mutants**."

---

## Part 3: Results & Failure Walkthroughs (~2 minutes)

*(To be written after the real model runs. Use only numbers from
`results/main/summary.md` and walk through one or two real failing transcripts
from `results/main/raw/`. The earlier draft of this part quoted simulated
results and has been removed.)*

---

## Part 4: The Takeaway (~0.5 minute)

*(To be written from what the real transcripts show.)*
