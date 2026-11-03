# OrderBook-DST: Deterministic Simulation Testing for Financial Exchange State Machines

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
- **Mutant kill rate**: 35 hand-crafted fault mutants (injecting realistic human bugs) are 100% killed by the grader suite, detecting every invariant violation.
- **Grader Validation Suite**: Full automated validation suite (`tools/validate_graders.py`) passes all checks V1 to V8.

---

## 5. Model Evaluation Results

> **Status: pending real model runs.** An earlier draft of this repository contained
> *simulated* results: a local script assigned reference, alt-reference and mutant
> code to each "trial" instead of calling any model. Those files, the transcripts
> built from them, and every number derived from them have been deleted
> (see `CHANGELOG.md`, *Corrected*). No model result is claimed until it comes from
> `harness/run_eval.py` calling a real provider API.

The table below is filled in from `results/main/summary.md` after the run:

| Model (exact ID, settings) | Trials / task | Pass rate | 95% CI | pass@5 | pass^5 | Mean score | T1 | T2 | T3 | Cost / full run |
|---|---|---|---|---|---|---|---|---|---|---|
| _frontier model A_ | 5 | – | – | – | – | – | – | – | – | – |
| _frontier model B_ | 5 | – | – | – | – | – | – | – | – | – |
| _smaller / open model_ | 5 | – | – | – | – | – | – | – | – | – |

Run date, git SHA, exact model IDs, settings, and per-trial token counts are
recorded in `results/main/run_meta.json` and `results/main/trials.jsonl`.

---

## 6. Hypotheses Under Test

The hypotheses were pre-registered in [`HYPOTHESES.md`](HYPOTHESES.md) before any
model run. Whether each one holds will be reported there from real transcripts:

- **H1, the generalization gap:** scores on visible tests (T1) will be higher than on hidden simulation traces (T3).
- **H2, the coupling penalty:** coupled handlers (Variant B) will be harder than isolated rules (Variant A). Caveat: B tasks are also longer and touch more state, and F4/F5 have no A variant (3 A tasks vs 5 B tasks), so a gap here does not isolate "coupling" alone. A and B tasks are different tasks, so the comparison is unpaired.
- **H3, invariant feedback:** structured invariant diagnostics will help repair a failed attempt (`--mode feedback_loop`).

---

## 7. Failure Walkthroughs

To be written by the author from the real transcripts in `results/main/raw/`,
with at least one failure per task, one task where a model came close, and a
judgement on each failure: real model mistake, or grader rejecting a valid answer.

---

## 8. Quickstart & Reproducibility

### Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 1. Run the test suite (no API keys needed)
```bash
make test
```

### 2. Validate the graders against the reference solutions and mutants (V1–V8)
```bash
make validate
```

### 3. Run the models
```bash
cp models.example.toml models.toml   # fill in exact model IDs, settings and prices
cp .env.example .env                 # fill in your own keys; .env is git-ignored
set -a; source .env; set +a
.venv/bin/python -m harness.run_eval --models models.toml --mode single_turn --dry-run
.venv/bin/python -m harness.run_eval --models models.toml --mode single_turn --out results/main
.venv/bin/python -m harness.run_eval --models models.toml --mode feedback_loop --out results/feedback
```
The run resumes if interrupted: completed trials are skipped.

### 4. Build the summary tables
```bash
PYTHONPATH=. .venv/bin/python harness/report.py --in results/main --out results/main
```
Computes bootstrap 95% confidence intervals, pass@k and pass^k.

---

## 9. Provenance & AI Use Disclosure

- **Provenance**: OrderBook-DST was built entirely from scratch for the micro1 Eval Hackathon (October 30 – November 9, 2026). The financial state machine specification (`docs/04_RULEBOOK.md`), invariants (`docs/05_INVARIANTS_AND_DATA.md`), tasks, mutants, and graders were designed specifically for this benchmark.
- **AI Tool Usage**:
  - Claude Sonnet 4.6 (Thinking) assisted in drafting initial scaffolding and unit test fixtures.
  - An independent clean-room AI subagent implemented the secondary reference solution (`reference_alt_v2/`) without seeing the primary reference code.
  - **Correction**: a local script (not part of the submission) produced simulated model results for an earlier draft. They were never real model output and have been removed; see [`AI_USE.md`](AI_USE.md).
  - **Human review**: the benchmark design, pre-registered hypotheses (`HYPOTHESES.md`), domain review (`EXPERT_REVIEW.md`) and task difficulty reasons (`task.toml`) were reviewed by the author. See [`AI_USE.md`](AI_USE.md) for full attribution.
