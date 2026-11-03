# OrderBook-DST: Deterministic Simulation Testing for Financial Exchange State Machines

[![Grader Validation](https://img.shields.io/badge/Graders-V1--V8%20PASS-brightgreen)](tools/validate_graders.py)
[![Mutant Kill Rate](https://img.shields.io/badge/Mutants-35%2F35%20(100%25)-blue)](mutants)
[![Dual Reference Diff](https://img.shields.io/badge/Dual--Reference-1.0000%20(0%20diff)-success)](reference_alt_v2)
[![Python Version](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue)](pyproject.toml)

OrderBook-DST is an evaluation benchmark measuring whether Large Language Models can write mathematically and architecturally sound code for mission-critical financial exchange state machines.

---

## 1. What It Tests

OrderBook-DST evaluates an AI model's ability to implement financial exchange core state machine components under strict physical conservation laws:
- Exact 64-bit integer fixed-point accounting ($10^{-6}$ micro-units, zero floats).
- Piecewise volume fee tier schedules with IEEE 754 round-half-even (bankers' rounding).
- In-flight order cancel/replace priority preservation and collateral margin lock adjustments.
- Stateful FIX protocol sequencing, out-of-order gap queue buffering, and session reset epochs.
- Two-stage margin liquidation waterfalls under price shocks.
- Multi-leg atomic basket order execution with complete rollback on partial failure.

---

## 2. Who It's For & Why It Matters (Real-World Relevance)

In electronic trading and clearing infrastructure (CME, Nasdaq, crypto derivatives exchanges, market makers), software bugs are not cosmetic—they cause immediate clearinghouse insolvency, unauthorized credit creation, or market-wide flash crashes:
- **Knight Capital (2012)**: Reused an obsolete internal operational flag in routing code, generating millions of unintended executions in 45 minutes, incurring a **\$440 million loss** and bankrupting the firm.
- **FTX / Alameda (2022)**: An architectural loophole in margin accounting exempting an account from liquidation created an unbacked **\$8 billion deficit**, breaching basic cash and position conservation laws ($I_1$).
- **LME Nickel Crisis (2022)**: Failure in margin waterfall and order deleveraging cascade dynamics forced an unprecedented multi-day market halt and billions in cancelled trades.

Traditional software testing (isolated unit tests) fails to catch these bugs because each function appears locally correct. **Deterministic Simulation Testing (DST)**—pioneered by TigerBeetle and FoundationDB—replays hundreds of thousands of pseudorandom state transitions over a single-threaded deterministic event loop, validating inviolable system conservation laws after every single transition.

---

## 3. Benchmark Tasks Overview

The benchmark consists of **8 tasks** grouped into **5 mechanism families**. To measure the **Component Coupling Penalty (Hypothesis H2)**, each family pairs an isolated pure transformation (**Variant A**) with an integrated multi-subsystem engine handler (**Variant B**):

| Task ID | Family | Variant | Subsystem Focus | Applicable Rules | Difficulty & Invariant Risk |
|---|---|---|---|---|---|
| `f1_fee_a` | F1 (Fees) | **A (Isolated)** | `exchange_core/rules/fee_rule.py` | R-F1, R-F2, R-F4 | Piecewise rate splitting across 30-day volume tiers; round-half-even ties. |
| `f1_fee_b` | F1 (Fees) | **B (Coupled)** | `exchange_core/handlers/settle.py` | R-M4, R-F1..4, R-B5 | Multi-account cash transfers; fee vault funding for maker rebates ($I_1$); volume update timing. |
| `f2_replace_a` | F2 (Replace) | **A (Isolated)** | `exchange_core/rules/replace_rule.py` | R-P1, R-P2, R-P3 | Asymmetric price-time priority retention; rejecting `new_qty <= cum_qty` on partial fills. |
| `f2_replace_b` | F2 (Replace) | **B (Coupled)** | `exchange_core/handlers/replace.py` | R-P1..5, R-U3 | Coupling book queue re-indexing ($I_3$) with margin lock updates using original locked rate ($I_2$). |
| `f3_fix_a` | F3 (FIX) | **A (Isolated)** | `exchange_core/rules/session_rule.py` | R-S1..7 | Out-of-order sequence gap detection, buffering, ascending drain order ($I_4$), and `PossDupFlag`. |
| `f3_fix_b` | F3 (FIX) | **B (Coupled)** | `exchange_core/handlers/fix.py` | R-S1..9 | Coupling FIX protocol state with matching engine event dispatch; reset epochs; zero duplicate dispatches ($I_4$). |
| `f4_waterfall_b` | F4 (Shock) | **B (Coupled)** | `exchange_core/handlers/shock.py` | R-W1..6 | Two-stage margin liquidation waterfall: Stage 1 cancellation margin release with rechecks before Stage 2 liquidation. |
| `f5_basket_b` | F5 (Basket) | **B (Coupled)** | `exchange_core/handlers/basket.py` | R-A1..5 | Atomic All-or-None multi-leg basket: full state restitution ($I_1, I_2, I_3$) and report suppression on abort. |

Detailed specifications for all rules are documented in [`docs/04_RULEBOOK.md`](docs/04_RULEBOOK.md).

---

## 4. Grading Architecture & Validation

Candidates are scored using a 3-tier progressive grading pipeline (`graders/dst_grader.py`):
$$\text{Score} = 0.20 \times T_1 + 0.30 \times T_2 + 0.50 \times T_3$$

- **Tier 1 (Visible Unit Tests, Weight 0.20)**: Public pytest suite embedded directly in the prompt. Tests basic API contract and edge cases.
- **Tier 2 (Targeted Checkpoints, Weight 0.30)**: 59 targeted multi-step boundary conditions (e.g. tie-breaking at exact halves, partial fill replacements, sequence gap closures, margin restoration).
- **Tier 3 (Hidden Deterministic Simulation Traces, Weight 0.50)**: 20 pseudo-random event traces (200 events each) evaluating the 4 core exchange invariants:
  - **$I_1$ (Cash & Asset Conservation)**: $\sum \text{Cash} + \text{FeeVault} = \text{InitialCash}$ and $\sum \text{Position} = 0$.
  - **$I_2$ (Collateral Lock Conservation)**: Account locked cash exactly matches required margin for all resting orders.
  - **$I_3$ (Sequence Monotonicity)**: Order IDs and queue priority timestamps strictly increment.
  - **$I_4$ (Deduplication & Monotonicity)**: Sequence gap buffers drain in strict order; duplicate messages rejected.

### Grader Reliability & Verification
- **Dual Clean-Room Reference Implementations**: Two independently authored reference solutions (`reference/` and `reference_alt_v2/`) both achieve **1.0000 across all 8 tasks**, with 0 mismatches across 272,000 generated events and 544,000 invariant checks.
- **100% Mutant Kill Rate**: 35 hand-crafted fault mutants (injecting realistic human bugs) are 100% killed by the grader suite, detecting every invariant violation.
- **Grader Validation Suite**: Full automated validation suite (`tools/validate_graders.py`) passes all checks V1 to V8.

---

## 5. Model Evaluation Results

We evaluated 3 frontier and open models across all 8 benchmark tasks (5 independent trials per task, 120 total trials) plus multi-turn feedback loop evaluation:

| Model (Version, Settings) | Trials / Task | Pass Rate (pass@1) | 95% Bootstrap CI | pass@5 | pass^5 | Mean Score | 95% CI | T1 (Public) | T2 (Checkpoints) | T3 (Hidden Traces) | MTTIF | Est. Cost / Run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Claude 3.5 Sonnet** (`20241022`, $T=0$) | 5 | **55.0%** | [30.0%, 80.0%] | **100.0%** | **25.0%** | **0.713** | [0.543, 0.875] | 0.893 | 0.789 | **0.596** | 82.4 | \$1.16 |
| **GPT-4o** (`2024-08-06`, $T=0$) | 5 | **37.5%** | [15.0%, 62.5%] | **75.0%** | **0.0%** | **0.619** | [0.456, 0.784] | 0.884 | 0.746 | **0.436** | 83.9 | \$0.84 |
| **Qwen 2.5 Coder 7B** (`Instruct`, $T=0$) | 5 | **10.0%** | [0.0%, 25.0%] | **37.5%** | **0.0%** | **0.439** | [0.335, 0.557] | 0.813 | 0.586 | **0.200** | 107.0 | \$0.18 |

*(Full structured trials data available in [`results/trials.jsonl`](results/trials.jsonl) and [`results/summary.json`](results/summary.json)).*

---

## 6. Key Findings & The "Hot Take"

### 1. The Generalization Deficit (Tier 1 vs Tier 3 Gap)
All models demonstrated a statistically significant drop from visible public tests ($T_1$) to hidden simulation traces ($T_3$):
- Claude 3.5 Sonnet: $T_1 = 0.893 \to T_3 = 0.596$ ($\Delta = +0.296$)
- GPT-4o: $T_1 = 0.884 \to T_3 = 0.436$ ($\Delta = +0.447$)
- Qwen 2.5 Coder: $T_1 = 0.813 \to T_3 = 0.200$ ($\Delta = +0.613$)

*Models easily satisfy prompt-visible test cases, but break when exposed to dynamic multi-event state trajectories.*

### 2. The Component Coupling Penalty (Hypothesis H2)
When comparing pure transformation functions (Variant A) to coupled multi-subsystem handlers (Variant B):
- **Claude 3.5 Sonnet**: Pass rate dropped from **93.3%** on Variant A to **32.0%** on Variant B (McNemar test $p = 0.0215$).
- **GPT-4o**: Pass rate dropped from **80.0%** on Variant A to **12.0%** on Variant B (McNemar test $p = 0.0156$).
- **Root Cause**: Over **72.9%** of Variant B failures were caused by omitting secondary state mutations (e.g. failing to debit the ledger fee vault when crediting maker rebates, or skipping margin lock adjustments) while the primary order execution logic was completely correct.

### 3. Invariant Feedback Loop Benefit (Hypothesis H3)
Providing models with structured invariant diagnostics (`[Invariant ID, Plain Name, Message]`) in a multi-turn feedback loop allowed Claude 3.5 Sonnet to repair secondary state omissions:
- **Turn 0 (No feedback)**: 0.0% pass rate on initial failed runs.
- **Turn 1 (With invariant feedback)**: **60.0% pass rate** (+60% revision gain).
- Full details in [`results/feedback_results.json`](results/feedback_results.json).

---

## 7. Representative Failure Walkthroughs

Representative failures with full transcripts and invariant diagnostic traces are cataloged in [`transcripts/FAILURES_ANALYSIS.md`](transcripts/FAILURES_ANALYSIS.md):

1. **`f1_fee_b` (Cash Conservation $I_1$ Failure)**: Model credited maker rebates directly into trader cash without debiting the exchange fee vault. Cash was created from thin air (`total money 160000124750 != initial 160000000000`).
2. **`f2_replace_b` (Margin Lock Conservation $I_2$ Failure)**: Model recalculated collateral locks using current engine default rate rather than preserving the order's historical locked margin rate.
3. **`f3_fix_b` (FIX Sequencing $I_4$ Failure)**: Model double-dispatched messages to the matching engine during sequence gap buffer drains.
4. **`f4_waterfall_b` (Inverted Waterfall Execution)**: Model initiated backstop liquidation against the `LIQ` account before cancelling resting orders to release locked margin, unnecessarily liquidating solvent accounts.
5. **`f5_basket_b` (Atomic Rollback Failure)**: On intermediate leg rejection, model reverted order book state but failed to restore ledger balances and leaked execution reports.

---

## 8. Quickstart & Reproducibility

### Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 1. Run Complete Test Suite
```bash
make test
```
*Executes all 242 engine unit tests and prompt leakage tests in ~8 seconds.*

### 2. Validate Graders & Mutants (V1 - V8)
```bash
make validate
```
*Validates reference solutions, clean-room alt references, and kills all 35 mutants.*

### 3. Generate Benchmark Reports
```bash
PYTHONPATH=. .venv/bin/python harness/report.py --in results/ --out results/
```
*Computes bootstrap 95% confidence intervals, pass@k, pass^k, and markdown summary table.*

---

## 9. Provenance & AI Use Disclosure

- **Provenance**: OrderBook-DST was built entirely from scratch for the micro1 Eval Hackathon (October 30 – November 9, 2026). The financial state machine specification (`docs/04_RULEBOOK.md`), invariants (`docs/05_INVARIANTS_AND_DATA.md`), tasks, mutants, and graders were designed specifically for this benchmark.
- **AI Tool Usage**:
  - Claude Sonnet 4.6 (Thinking) assisted in drafting initial scaffolding and unit test fixtures.
  - An independent clean-room AI subagent implemented the secondary reference solution (`reference_alt_v2/`) without seeing the primary reference code.
  - **Human Expert Review & Sign-Off**: The benchmark design, pre-registered hypotheses (`HYPOTHESES.md`), domain expert review (`EXPERT_REVIEW.md`), task difficulty justifications (`task.toml`), and final transcripts analysis (`transcripts/FAILURES_ANALYSIS.md`) were thoroughly audited and signed off by the author. See [`AI_USE.md`](AI_USE.md) for full attribution.
