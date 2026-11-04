# OrderBook-DST: 5-Minute Video Walkthrough Script

*Designed per Section 6 (page 19) of the micro1 Eval Hackathon Participant Guide.*

---

## Part 1: The problem and why it matters (~1 minute)

**[Visual: title slide, then the f1_fee_b instruction]**

"OrderBook-DST asks one question: can a model write exchange-core code that stays
correct over hundreds of events, not just on the tests it can see?

In trading and clearing systems a bug moves money immediately. Knight Capital lost
about 440 million dollars in 45 minutes when old code was left reachable. FTX's
accounting let one account run a multi-billion-dollar hole. These are not crashes;
they are code that looks right and quietly breaks a conservation law.

So instead of asking a model about finance, I give it one file of a working
exchange engine to write, from a written rulebook, and then I run it."

---

## Part 2: How a task looks and how it is graded (~1.5 minutes)

**[Visual: task table from the README, then `make demo` in a terminal]**

"There are 8 tasks: tiered fees, cancel/replace priority, FIX sequence gaps, a
liquidation waterfall, and atomic multi-leg baskets. Three families come in two
versions: an isolated rule, and the handler that must also update everything
around it.

Grading is all code, three tiers. The visible tests from the prompt. 59 hidden
checkpoints. And 20 hidden simulations of 200 events each, replayed against a
reference engine, checking after every event that no money is created, margin
locks match resting orders, IDs only go up, and FIX replays give the same state.

Here is why the last tier matters. *(run `make demo`)* This bug changes one word:
it re-locks margin at today's rate instead of the order's original rate. It passes
every visible test and every checkpoint. The simulation catches it on all 20
seeds: invariant I2, order 31's lock is wrong.

I validated the grader before running any model: the reference and a clean-room
second reference written without seeing the first both score 1.0 on every task;
all 36 hand-written bugs fail; empty and hard-coded stubs score near zero; and
grading is deterministic. Of those 36 bugs, 33 are already caught by the visible
tests, so the question for the models is whether their mistakes look like mine."

---

## Part 3: Results & Failure Walkthroughs (~2 minutes)

*(To be written after the real model runs. Use only numbers from
`results/main/summary.md` and walk through one or two real failing transcripts
from `results/main/raw/`. The earlier draft of this part quoted simulated
results and has been removed.)*

---

## Part 4: The Takeaway (~0.5 minute)

*(To be written from what the real transcripts show.)*
