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

**[Visual: Results Summary Table and Transcript Diff from `transcripts/FAILURES_ANALYSIS.md`]**

**Speaker**:
"We evaluated 3 model cohorts across 5 trials per task—120 total trials:
- **Claude 3.5 Sonnet** achieved a **55.0% pass rate** (Mean score 0.713).
- **GPT-4o** achieved a **37.5% pass rate** (Mean score 0.619).
- **Qwen 2.5 Coder 7B** achieved a **10.0% pass rate** (Mean score 0.439).

Notice two crucial findings:

First, the **Generalization Deficit**:
Every single model easily passed the visible unit tests in Tier 1—scoring 81% to 89%. But when evaluated against Tier 3 hidden simulation traces, scores collapsed: Claude fell to 59.6%, GPT-4o fell to 43.6%, and Qwen dropped to 20.0%. Models easily overfit prompt-visible unit tests, but fail on long-horizon state trajectories.

Second, the **Component Coupling Penalty**:
On isolated Variant A tasks, Claude achieved a **93.3% pass rate**. But on coupled Variant B tasks, its pass rate plummeted to **32.0%**—a statistically significant drop ($p = 0.0215$).

Let's look at why models fail by walking through a real transcript from Task `f1_fee_b`:

**[Visual: Highlight code in `transcripts/claude_3_5_sonnet/f1_fee_b_trial_3.md`]**

In `f1_fee_b`, the model correctly calculates the trade fill and credits the maker rebate to the seller's account. But it forgets to debit the rebate from the exchange fee vault. The primary trade logic was completely correct, but total system cash increased from \$160,000,000 to \$160,001,247. Invariant $I_1$ caught the unauthorized cash creation at step 2.

In fact, **72.9% of all failures on coupled tasks were secondary state omissions**—forgetting to debit fee vaults, omitting margin lock adjustments, or skipping sequence counter increments."

---

## Part 4: The Hot Take & Invariant Feedback (~0.5 minute)

**[Visual: Multi-turn feedback diagram and `results/feedback_results.json`]**

**Speaker**:
"Our headline insight is that **unit tests give models a false sense of correctness in stateful distributed systems**.

To test how to bridge this gap, we implemented an **Invariant Feedback Loop**. When Claude 3.5 Sonnet was given structured invariant diagnostic reports—without revealing test inputs or seeds—its pass rate jumped from **0.0% on initial failure to 60.0% on Turn 1**.

Invariant-based feedback provides the exact orthogonal signal models need to overcome architectural tunnel vision.

OrderBook-DST is fully reproducible with a single `make validate` command, completely free of external API dependencies, and ready for evaluation. Thank you!"
