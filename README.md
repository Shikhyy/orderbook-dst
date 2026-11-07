# OrderBook-DST

**Can a model write exchange-core code that stays correct across hundreds of events, not just on the tests it can see?**

OrderBook-DST gives a model one file of a working exchange engine to implement (fee settlement, cancel/replace, FIX session handling, a liquidation waterfall, or atomic baskets), with a written rulebook and visible unit tests. The grader then replays 20 hidden, seeded 200-event simulations against a reference engine and checks four conservation invariants after every event: the deterministic-simulation-testing (DST) approach used for databases and ledgers.

> **Video walkthrough:** _link to be added before submission._
>
> **Summary.** 17 tasks in 9 families, graded by public tests, hidden checkpoints and 20 hidden seeded simulations. Seven free-tier models were run (329 trials, all real API calls; $0). The strongest model passes every task, so the benchmark separates small and mid models (36% to 82% pass rate on F1 to F8) and not the top. The visible tests overstate quality for the weaker models, and a hidden-simulation grader caught bugs that a careful read-through missed. An earlier draft contained simulated results; they were removed (see [`AI_USE.md`](AI_USE.md)).

---

## 1. What it tests

Whether a model can implement a stateful financial component exactly to a written spec — integer fixed-point money, priority rules, sequence handling, rollback — so that no money is created or lost and every side effect (fee vault, margin locks, counters, reports) is updated, over long random event sequences.

## 2. Who relies on this, and what a failure costs

Exchanges, clearing houses, brokers and crypto venues run matching and risk engines whose bugs move real money instantly. The tasks model failure classes that have caused real losses:

- **Side effects left out of a code path.** Knight Capital (2012): a deployment left old code reachable through a repurposed flag; in about 45 minutes the firm lost roughly \$440M and needed a rescue.
- **Accounting that does not conserve money.** FTX/Alameda (2022): an account exempt from normal liquidation and allowed a negative balance left a multi-billion-dollar hole.
- **Risk waterfalls under a price shock.** LME nickel (2022): a price spike overwhelmed margining; the exchange halted the market and cancelled trades.

A model that writes plausible-looking settlement code which silently credits a rebate without debiting the fee vault produces exactly this kind of bug. A reviewer reading one function will not see it; a conservation check over many events will.

## 3. Tasks

17 tasks in 9 families: 11 implementation tasks (F1–F8) and 6 diagnose-and-fix tasks (F9). Families F1–F3 have an isolated rule function (**A**) and an engine handler that must also update the surrounding state (**B**). Everything the grader checks is stated in the task's instruction and in [`docs/04_RULEBOOK.md`](docs/04_RULEBOOK.md).

| Task | Variant | File the model writes | Why it is hard (stated before any model run) |
|---|---|---|---|
| `f1_fee_a` | A | `rules/fee_rule.py` | A fill that crosses a volume tier must be split per tier, with round-half-even on each segment in integer math. |
| `f1_fee_b` | B | `handlers/settle.py` | Rebates must be paid out of the fee vault (I1), and volume must update *after* the fee is computed (R-B5). |
| `f2_replace_a` | A | `rules/replace_rule.py` | Priority is kept only on a size decrease; `new_qty <= cum_qty` must be rejected on partially filled orders. |
| `f2_replace_b` | B | `handlers/replace.py` | The margin lock must be recomputed at the order's *original* rate (I2), and the book queue re-indexed on priority loss (I3). |
| `f3_fix_a` | A | `rules/session_rule.py` | Detect sequence gaps, buffer, drain in ascending order, and apply PossDupFlag semantics. |
| `f3_fix_b` | B | `handlers/fix.py` | Couple the session to engine dispatch: no message dispatched twice, reset epochs handled (I4). |
| `f4_waterfall_b` | B | `handlers/shock.py` | Stage 1 cancels orders and re-checks solvency *before* Stage 2 liquidates, in the specified account order. |
| `f5_basket_b` | B | `handlers/basket.py` | An aborted basket must restore every piece of state — book, cash, locks, volume, counters — and emit no reports. |
| `f6_match_b` | B | `handlers/new_limit.py` | The whole matching handler: validation order, price-time matching across levels, self-trade prevention that cancels resting orders mid-sweep, IOC remainder, all coupled with fee settlement. |
| `f7_funding_b` | B | `handlers/funding.py` | Funding between longs and shorts: clamped rate, rounding on the absolute amount, payer by position and rate sign, the rounding residual into the fee vault, and a mandatory waterfall afterwards. |
| `f8_adl_b` | B | `handlers/bankruptcy.py` | After a liquidation leaves negative cash: a capped fee-vault draw, then pro-rata loss sharing among the other side (excluding `LIQ`), floor shares, leftover units by weight then string id order, reports in order, money conserved exactly. |

### F9: diagnose and fix (6 tasks, exploratory)

The 11 tasks above ask a model to *implement* a handler from a written specification. F9 asks for a different skill: *finding a defect from its symptom*. Each `f9_dbg_N` task gives the model the specification of an existing task, the handler file with **one defect** (a sanitised copy of one of the hand-written mutants), and a bug report: a short fixed event trace and the first thing that goes wrong when the buggy engine runs it (a wrong report, a broken invariant, or a wrong balance). The model returns the corrected file. It is graded by the grader of the task it is graded as (`grades_as` in `task.toml`): same public tests, checkpoints and hidden seeds, so a correct fix scores 1.0.

| Task | Graded as | Defect (never shown to the model) |
|---|---|---|
| `f9_dbg_1` | `f1_fee_b` | Volume is added before the taker fee is computed, so the tier comes from a volume that already contains the fill. |
| `f9_dbg_2` | `f4_waterfall_b` | No breach re-check after stage 1, so a cured account is still liquidated. |
| `f9_dbg_3` | `f5_basket_b` | A rolled-back basket keeps the advanced order-id counter. |
| `f9_dbg_4` | `f6_match_b` | A partially filled resting order releases margin but keeps its old stored lock. |
| `f9_dbg_5` | `f7_funding_b` | The rounding residual of the funding payments is never booked to the fee vault. |
| `f9_dbg_6` | `f8_adl_b` | Leftover loss units go to the largest fractional remainders instead of the largest weights. |

Per-instance notes (why the symptom is not obvious, why the fix is unique) are in [`docs/F9_INSTANCES.md`](docs/F9_INSTANCES.md). The symptom comes from `tools/make_f9.py` (run the buggy and the reference engine on a fixed visible trace; no model involved), so it is reproducible. F9 is **not** part of the pre-registered hypotheses H1–H5 and is kept out of the headline table; `make report` lists it in its own section next to the same model's result on the implementation task. Whether models are weaker at diagnosis than at implementation is an open question until the runs exist.

All data is synthetic: the rulebook, accounts and event traces are generated for this benchmark.

## 4. Grading and grader validation

`graders/dst_grader.py` scores every attempt with code, not an LLM judge:

**score = 0.2 · T1 + 0.3 · T2 + 0.5 · T3**, pass = score 1.0

- **T1, visible tests** (in the prompt): the public pytest file for the task.
- **T2, checkpoints** (hidden): 87 targeted multi-step scenarios across the 11 tasks (exact tie rounding, partial-fill replaces, gap closure, rollback).
- **T3, hidden simulation** : 20 seeded traces × 200 events. After each event the candidate engine must emit the same reports as the reference (D1) and satisfy I1 cash/position conservation, I2 margin locks match resting orders, I3 order IDs and priorities strictly increase, and I4 FIX replay with duplicates and gaps gives the same state.

Partial credit is built in (tier scores are fractions of tests, checkpoints and seeds passed). The grader checks the final behaviour of the code, not how it was written.

### How the grader was validated (run it: `make validate`, ~2 min)

| Check | Result |
|---|---|
| V1 Reference solution passes every tier, all 11 tasks, graded exactly as a model's answer (same import allowlist) | PASS |
| V2 Clean-room second reference (`reference_alt_v2/`, written without seeing `reference/`) passes, all 11 tasks, same rules | PASS |
| V3 All 77 hand-written bug mutants fail, each with the invariant its `expect.toml` predicts | PASS |
| V4 / V5 Empty stub and hard-coded-answer stub score near 0 (cannot game T3) | PASS |
| V6 Grading is deterministic (same code → same score) | PASS |
| V7 Every hidden trace exercises the task's code path ≥ 10 times | PASS |
| D1–D5 (each F9 task): the reference, the clean-room alternative and a minimal hand-written fix score 1.0; the buggy file scores below 1.0 exactly like its source mutant; the stored symptom reproduces | PASS |
| V8 Mutants trigger I1 and I2, not only report mismatches | PASS |

Also tested (`make test`, 547 tests): prompts never contain hidden seeds, checkpoint values or reference code; candidate imports are restricted to an allowlist; secrets never reach saved replies; report statistics are recomputed from raw records.

### Which tier catches which bug (`make mutant-tiers`, no API calls)

Running all 81 mutants through the grader ([`results/grader_analysis/mutant_tiers.md`](results/grader_analysis/mutant_tiers.md)):

- **54 / 81** fail at least one *visible* test; 21 more are caught first by the hidden checkpoints; **6** pass every visible test and every checkpoint and are caught only by the hidden simulation: `f2_replace_b/m_lock_uses_current_rate` (a one-token change, `state.margin_bps` for `order.margin_bps`, that fails all 20 seeds on I2; run `make demo` to see it), three in `f6_match_b` (`m_post_only_ignores_own`, 13 of 20 seeds; `m_relock_current_rate`, the same one-token bug in the resting-order relock, 19 of 20; `m_stp_stops_matching`, 20 of 20) and two in `f7_funding_b` (`m_skips_negative_cash`: skipping funding for accounts whose cash is already negative, 20 of 20; `m_qty_skips_zero_amount`: not counting accounts whose amount rounds to 0, 8 of 20).
- So for the bugs the author anticipated, the visible tests are already strong. The open question the model runs answer is whether **model** bugs look like these, or are the kind only long simulations reveal.
- The hidden simulation also compares the **whole final engine state** with the reference's (not only balances). This was added after the first real run: a model skipped a required state update (storing the new mark price) that no report, invariant or balance revealed, and still scored a perfect T3. `f4_waterfall_b/m_mark_price_not_stored` reproduces it and fails all 20 seeds.
- The grader compares reports before checking invariants, so a bug that breaks conservation *and* changes a report would be labelled D1. The grader now also records every invariant broken at each seed's first failing event; this does not change any score, but it is what the H5 analysis uses.

## 5. Results

Copied unchanged from [`results/main/summary.md`](results/main/summary.md) (`make report`, 329 trials, regraded with the current grader at `e781834`+, single-turn, 3 trials per task and model; graded with the Nov 6 grader, see `CHANGELOG.md`). Every trial's prompt, raw reply, extracted files and score are under `results/main/raw/`.

**One model is incomplete.** `gemini_35_flash` has 23 of 33 headline trials and 0 of 18 F9 trials: the free Gemini tier returned HTTP 429 repeatedly and the harness gave up after 6 retries per trial, across several resumes. Its row is over the trials that exist, so it is not directly comparable with the complete rows; it is missing all trials of `f3_fix_b`, `f7_funding_b` and `f8_adl_b` and one `f6_match_b` trial. Every other model has all of its trials.

### Headline results (F1 to F8, 11 tasks)

| Model (ID, settings) | Trials / task | Pass rate | 95% CI | pass@k | pass^k | Mean score | 95% CI | T1 | T2 | T3 | Cost (run) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **nemotron_ultra** (`nvidia/nemotron-3-ultra-550b-a55b:free`, max_tokens=16000, api_key_env=OPENROUTER_API_KEY) | 3 | 100.0% | [1.00, 1.00] | 100.0% | 100.0% | 1.000 | [1.00, 1.00] | 1.00 | 1.00 | 1.00 | $0.00 |
| **mistral_large** (`mistral-large-4`, max_tokens=8000, api_key_env=MISTRAL_API_KEY) | 3 | 93.9% | [0.82, 1.00] | 100.0% | 81.8% | 0.960 | [0.87, 1.00] | 0.97 | 0.97 | 0.95 | $0.00 |
| **gemma_26b** (`gemma-4-26b-a4b-it`, max_tokens=8000, api_key_env=GEMINI_API_KEY) | 3 | 81.8% | [0.58, 1.00] | 90.9% | 72.7% | 0.846 | [0.63, 1.00] | 0.91 | 0.85 | 0.82 | $0.00 |
| **flash_lite** (`gemini-3.1-flash-lite`, max_tokens=8000, api_key_env=GEMINI_API_KEY) | 3 | 78.8% | [0.58, 0.97] | 100.0% | 63.6% | 0.861 | [0.71, 0.98] | 0.96 | 0.87 | 0.82 | $0.00 |
| **nemotron_nano** (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`, max_tokens=16000, api_key_env=OPENROUTER_API_KEY) | 3 | 36.4% | [0.12, 0.61] | 54.5% | 18.2% | 0.420 | [0.19, 0.67] | 0.49 | 0.41 | 0.40 | $0.00 |
| **ministral_8b** (`ministral-8b-latest`, max_tokens=8000, api_key_env=MISTRAL_API_KEY) | 3 | 36.4% | [0.09, 0.64] | 45.5% | 27.3% | 0.508 | [0.30, 0.73] | 0.80 | 0.56 | 0.37 | $0.00 |
| **gemini_35_flash** (`gemini-3.5-flash`, max_tokens=16000, api_key_env=GEMINI_API_KEY) | 3 | 87.5% | [0.62, 1.00] | 87.5% | 87.5% | 0.935 | [0.81, 1.00] | 1.00 | 1.00 | 0.87 | $0.00 |

Pass = score 1.0 (all public tests, all checkpoints and all 20 hidden seeds). pass@k: at least one of k trials passes; pass^k: all k pass. CIs are a hierarchical bootstrap over tasks, then trials. Cost uses the per-model prices in `models.toml` (0 if not set).

### Per task (passes / trials, mean score)

| Task | nemotron_ultra | mistral_large | gemma_26b | flash_lite | nemotron_nano | ministral_8b | gemini_35_flash |
|---|---|---|---|---|---|---|---|
| `f1_fee_a` | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) |
| `f1_fee_b` | 3/3 (1.00) | 3/3 (1.00) | 0/3 (0.00) | 3/3 (1.00) | 0/3 (0.00) | 2/3 (0.67) | 3/3 (1.00) |
| `f2_replace_a` | 3/3 (1.00) | 2/3 (0.89) | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) |
| `f2_replace_b` | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 1/3 (0.43) | 0/3 (0.07) | 0/3 (0.30) | 3/3 (1.00) |
| `f3_fix_a` | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 2/3 (0.67) | 3/3 (1.00) | 3/3 (1.00) |
| `f3_fix_b` | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 2/3 (0.67) | 1/3 (0.63) | – |
| `f4_waterfall_b` | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 1/3 (0.68) | 1/3 (0.33) | 0/3 (0.09) | 3/3 (1.00) |
| `f5_basket_b` | 3/3 (1.00) | 3/3 (1.00) | 2/3 (0.73) | 1/3 (0.63) | 0/3 (0.16) | 0/3 (0.42) | 0/3 (0.50) |
| `f6_match_b` | 3/3 (1.00) | 2/3 (0.67) | 1/3 (0.57) | 3/3 (1.00) | 0/3 (0.00) | 0/3 (0.09) | 2/2 (1.00) |
| `f7_funding_b` | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 0/3 (0.07) | 0/3 (0.21) | – |
| `f8_adl_b` | 3/3 (1.00) | 3/3 (1.00) | 3/3 (1.00) | 2/3 (0.72) | 1/3 (0.65) | 0/3 (0.18) | – |

### F9: diagnose and fix (exploratory, not in the headline table or H1 to H5)

The model gets the specification, a handler with one defect and the first failing step of a short trace, and returns the corrected file. Each task is graded exactly like the task it is graded as. These trials are not in the headline table or in H1–H5. `impl` is the same model's passes on the implementation task (written from scratch) that the F9 task is graded as.

| Task (graded as) | nemotron_ultra | mistral_large | gemma_26b | flash_lite | ministral_8b | nemotron_nano |
|---|---|---|---|---|---|---|
| `f9_dbg_1` (`f1_fee_b`) | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 0/3 | 3/3 (1.00), impl 3/3 | 0/3 (0.08), impl 2/3 | 3/3 (1.00), impl 0/3 |
| `f9_dbg_2` (`f4_waterfall_b`) | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 1/3 | 3/3 (1.00), impl 0/3 | 0/3 (0.00), impl 1/3 |
| `f9_dbg_3` (`f5_basket_b`) | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 0/3 (0.38), impl 2/3 | 3/3 (1.00), impl 1/3 | 0/3 (0.38), impl 0/3 | 1/3 (0.33), impl 0/3 |
| `f9_dbg_4` (`f6_match_b`) | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 2/3 | 3/3 (1.00), impl 1/3 | 3/3 (1.00), impl 3/3 | 2/3 (0.74), impl 0/3 | 1/3 (0.33), impl 0/3 |
| `f9_dbg_5` (`f7_funding_b`) | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 2/3 (0.68), impl 0/3 | 2/3 (0.67), impl 0/3 |
| `f9_dbg_6` (`f8_adl_b`) | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 2/3 | 3/3 (1.00), impl 0/3 | 3/3 (1.00), impl 1/3 |

### H3: invariant feedback loop

From [`results/feedback/summary.md`](results/feedback/summary.md) (`--mode feedback_loop`, 30 trials: `gemma_26b` and `flash_lite` on `f1_fee_b`, `f2_replace_b`, `f4_waterfall_b`, `f5_basket_b`, `f6_match_b`, 3 trials each; graded with the current grader):

| Model | Trials | Turn 0 pass | Final pass | Mean score gain | Fixed / broken | McNemar p | Mean revisions |
|---|---|---|---|---|---|---|---|
| gemma_26b | 15 | 60.0% | 100.0% | +0.347 | 6 / 0 | 0.031 | 0.47 |
| flash_lite | 15 | 60.0% | 93.3% | +0.243 | 5 / 0 | 0.062 | 0.67 |

### Claude Sonnet reference run (not reproducible, not in the headline)

To get one data point from a strong closed model without paid API access, six trials (3 each on `f5_basket_b` and `f6_match_b`, the two hardest implementation tasks) were answered by fresh Claude Sonnet subagents inside Claude Code. Each subagent was given only the exact harness prompt (same prompt hash as the other models) as a file, wrote one reply file, and had no repository access. The transcripts show one read of the prompt file and one write of the reply for each. The replies were extracted and graded with the same extractor and the same three-tier grader (`tools/ingest_reply.py`); results are in `results/claude/`.

| model | task | trials | pass |
|---|---|---|---|
| claude_sonnet (interactive) | f5_basket_b | 3 | 3/3 (1.000) |
| claude_sonnet (interactive) | f6_match_b | 3 | 3/3 (1.000) |

Reading: a strong closed model implements both of the hardest tasks from the specification alone, which extends the top-end saturation seen with `nemotron_ultra` and `mistral_large` to a closed frontier model. Caveats: six trials only; it cannot be rerun through the harness; and Claude models helped draft parts of this project (see `AI_USE.md`), so familiarity with the domain cannot be ruled out. It is reported separately and does not enter any table above.

### Human Audit Agreement

A sample of 20 trials (10 the grader passed, 10 it failed; seed 42, drawn from 209 judgeable trials; no-code trials and F9 excluded) was read against the task instructions without seeing the grader verdict. Full table: [`results/human_audit.md`](results/human_audit.md). The original verdicts are kept in `results/my_verdicts_initial.json`.

**Blind result (headline).** The reviewer marked 19 of 20 correct. Raw agreement 11/20 (55%), Cohen's kappa 0.10 (slight). All nine disagreements were grader-failed trials marked correct; the reviewer never marked a grader-passed trial incorrect. The one agreed failure is T08 (ministral_8b, f6_match_b: bids sorted the wrong way for SELL orders).

**Unblinded re-review (not independent).** The reviewer then re-read only the nine grader-failed trials they had marked correct, knowing the grader had failed them, and changed 8 to incorrect after finding real bugs (crashes on attributes that do not exist, an uninitialised `leaves`, a basket rollback that never triggers, a stale `free_cash` in the R-W4 re-check). The ten grader-passed trials got no second look. This gives raw agreement 19/20 and kappa 0.90, but it shows only that the reviewer can find the bug once told where to look. It is not independent agreement.

| (after re-review) | reviewer: correct | reviewer: incorrect |
|---|:---:|:---:|
| grader PASS | 10 | 0 |
| grader FAIL | 1 | 9 |

- The remaining disagreement, T05 (flash_lite, f5_basket_b), is a reviewer error, found by an AI cross-check and not by the author: the code fails an IOC leg on any `CANCELLED` report, but R-A3 fails it only on an `IOC_REMAINDER` cancellation. A self-trade-prevention cancel inside a successful leg therefore triggers a rollback, on all 20 hidden seeds. The grader was right. With T05 corrected, agreement would be 20/20.
- **Reading.** A read-through against a long rulebook missed 9 of the 10 failures the hidden seeds caught. In every disagreement I checked, the grader was right. This is evidence for the grader, and for how hard these bugs are to see by reading. It is not a measured human-grader agreement of 0.90.

## 6. Pre-registered hypotheses

Written and committed (`3fea5fd`) before any model run; see [`HYPOTHESES.md`](HYPOTHESES.md). `harness/report.py` computes each one the same way for every model:

| | Prediction | Computed as |
|---|---|---|
| H1 | Visible-test score exceeds hidden-simulation score | Mean of per-trial T1 − T3, hierarchical bootstrap CI; trials with extraction errors excluded |
| H2 | Variant B is harder than Variant A | Per-family A − B pass rate and score over F1–F3, one-sided stratified permutation test (A and B are different tasks, so this is unpaired; B tasks are also bigger, so a gap is not attributable to coupling alone) |
| H3 | Invariant feedback lets a model repair a failed attempt | First vs final turn on the *same* trial (`--mode feedback_loop`), exact McNemar test |
| H4 | Frontier models break I1/I2 less than small models | Share of hidden seeds without each invariant violated |
| H5 | Most Variant B failures are missed side effects, not wrong core logic | Share of failing B seeds where a conservation invariant broke vs report mismatch only (an automatic proxy; checked against transcripts) |

Computed values (from `results/main/summary.md`; the reading of each hypothesis is in [`HYPOTHESES.md`](HYPOTHESES.md) section 3, still to be written by the author):

| Model | H1: T1 − T3 [95% CI] | H2: A − B pass rate (p) | H2: A − B score (p) | H4: I1 / I2 seed survival | H5: conservation share of B failing seeds |
|---|---|---|---|---|---|
| nemotron_ultra | 0.000 [0.00, 0.00] | 0.000 (p=1.000) | 0.000 (p=1.000) | 1.00 / 1.00 | – of 0 |
| mistral_large | 0.015 [0.00, 0.06] | -0.111 (p=1.000) | -0.036 (p=1.000) | 1.00 / 1.00 | – of 0 |
| gemma_26b | 0.096 [0.00, 0.27] | 0.333 (p=0.053) | 0.333 (p=0.053) | 1.00 / 1.00 | 33% of 60 |
| flash_lite | 0.143 [0.02, 0.31] | 0.222 (p=0.207) | 0.189 (p=0.207) | 0.97 / 1.00 | 20% of 101 |
| nemotron_nano | 0.202 [0.00, 0.48] | 0.667 (p=0.009) | 0.644 (p=0.009) | 0.94 / 1.00 | 32% of 59 |
| ministral_8b | 0.504 [0.26, 0.74] | 0.667 (p=0.005) | 0.468 (p=0.005) | 0.81 / 0.90 | 67% of 299 |
| gemini_35_flash | 0.125 [0.00, 0.38] | 0.000 (p=1.000) | 0.000 (p=1.000) | 1.00 / 1.00 | 0% of 60 |

- H1 is paired within each trial; trials with extraction or tier 1/2 errors are excluded.
- H2 uses only families with both variants (F1–F3) and a one-sided stratified permutation test. A and B are different tasks, so this is not a paired test, and B tasks are also larger, so the gap is not attributable to coupling alone.
- H4/H5 use every failing hidden seed, with all labels seen at its first failing event. H5's split (conservation law broken vs report mismatch only) is an automatic proxy for the pre-registered 'secondary omission vs primary logic' classification and must be checked against the transcripts.

## 7. Failure analysis

*Drafted with AI assistance from `docs/FAILURE_REVIEW.md` and `docs/FACT_SHEET.md` (see [`AI_USE.md`](AI_USE.md)); every number is from `results/main/summary.md`. Verbatim failing transcripts are in `transcripts/`.*

**What the failures were (221 headline trials, F1 to F8).** 161 passed. Of the 60 failures, 32 ran but behaved wrongly, 16 crashed in a tier, and 12 were truncated at the shared token limit (11 of them `nemotron_nano`), so there was no code to grade. Truncation is a token-budget effect and is reported apart from logic failures.

**Where models fail, and why.**
- **Invented engine interfaces (crashes).** Weaker models call attributes that do not exist (`Engine.orders`, `Engine.accounts`, `Engine.book`, `engine.mark_price`) or call module-level ledger functions as methods. The code crashes as soon as the simulation replays an event. This is the main failure of `nemotron_nano` and `ministral_8b` on F1, F2 and F4.
- **Missing all-or-nothing rollback (F5, the hardest task, 9 of 21 passes).** Models emit per-leg reports instead of rolling the whole basket back, detect a failed leg from a report that is never produced, or treat any `CANCELLED` report as a failed leg, so a self-trade-prevention cancel inside a successful leg triggers a false rollback.
- **Stale state in the waterfall (F4).** Models read `free_cash` before Stage 1 cancellations and re-use it in the Stage 2 re-check.
- **Matching details (F6).** Best-price selection and bid sorting for SELL orders, a filled order left on the book, wrong `leaves`, and self-trade-prevention ordering.
- **Rounding at the edge (F7).** `nemotron_nano` lost 2 units of money to rounding.
- **What the visible tests hide.** `ministral_8b` loses 0.50 of score between the visible tests and the hidden simulations (H1, interval excludes 0) and `flash_lite` 0.14; `nemotron_ultra` loses 0.

**Feedback helps.** With invariant feedback (H3), `gemma_26b` went from 60% to 100% (6 repaired, 0 broken, p = 0.031) and `flash_lite` from 60% to 93% (5 repaired, 0 broken, p = 0.062), on two models and five tasks.

**Honest limits of the result.** `nemotron_ultra` passed all 51 trials and `mistral_large` failed 2 of 51. Four designs (F6, F7, F8, F9) were built to break the strongest model and none did. A Claude Sonnet reference run passed 6 of 6 on the two hardest tasks (see §5). On these models a clear specification is enough, so the benchmark separates weak and mid models, not the top. No closed frontier model was run through the harness.

**Defects in my own work that the checks found.** Nine task or grader defects were found and fixed, each invalidating or changing results, including a withdrawn simulated analysis, an F3 specification gap (the `body=None` rule), an ambiguous F7 rule that made 4 of 5 early failures spurious, and four wrong implementations that scored 1.0 until checkpoints and mutants were added (`docs/FAILURE_REVIEW.md`).

## 8. Reproduce it

Requirements: Python 3.12 or newer (tested on 3.12 and 3.14), dependencies pinned in `requirements.txt`. No API key is needed for steps 1–3.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make test            # 549 tests, ~30 s
make validate        # grader validation V1-V8, ~45 s
make demo            # one bug that only the hidden simulation catches, ~3 s
make mutant-tiers    # which tier catches each of the 81 bugs, ~20 s
```

Clean environment with Docker:

```bash
docker build -t orderbook-dst . && docker run --rm orderbook-dst
```

(The Docker path was not verified on the author's machine; the virtual-environment route above is the tested one.)

Run models on **free tiers** (no payment method needed; `.env` and `models.toml` are git-ignored):

```bash
cp models.free.example.toml models.toml   # Gemini, NVIDIA NIM, Groq (+ optional Mistral, OpenRouter, Cerebras)
cp .env.example .env                      # add the free keys you created; never commit or paste them
set -a; source .env; set +a
make list-models                          # exact model IDs your keys can use -> put them in models.toml
make dry-run                              # calls per model, no API calls
make pilot                                # 1 trial per task: checks reply format, truncation, headroom
make watch                                # in a second terminal: live progress, current wait, ETA (make status = one snapshot)
make run                                  # 17 tasks x 3 trials per model -> results/main
#   (add ONLY=label1,label2 to run some models, e.g. while one provider is down)
make feedback TASKS=f1_fee_b,f2_replace_b,f3_fix_b,f4_waterfall_b,f5_basket_b TRIALS=3
make report transcripts                   # tables, sanity checks, representative transcripts
```

Every trial prints a counter line (`[12/40] ... ETA ~25m`), rate-limit waits and retries are announced instead of silent, and `make status` / `make watch` show progress from another terminal (reads `results/<run>/progress.json`). A provider that returns an empty reply (for example `finish_reason=tool_calls` with no tool offered) is asked again up to twice, and the retry count is stored in the trial record.

Free tiers have per-minute and per-day caps. Set `rpm` and `rpd` per model from your provider dashboard: the harness spaces calls, retries 429/5xx with backoff, and when a daily cap is reached it stops that model cleanly. Run the same command again after the reset and it resumes; a quota error is never recorded as a model failure. Prompts are about 5–7k tokens; the harness warns when a provider reports far fewer input tokens than the prompt has (a truncated prompt is not a task failure). Paid APIs work the same way with `models.example.toml`.

**Settings.** Temperature is not sent (provider defaults); `max_tokens` is per model in the results tables. Single-turn runs were made 4 to 6 November 2026 (UTC), with later reruns and regrades through 7 November.

Optional reasoning-effort ablation (more effort should not score worse; if it does, suspect the task): `models.ablation.example.toml`.

**Cost and runtime.** Each call sends about 5.3k–6.6k input tokens; a single-turn run is 51 calls per model (17 tasks x 3 trials), a feedback run up to 4 calls per trial. On free tiers the cost is $0; the limit is the daily request cap (for example ~45 calls/day means one model's single-turn run takes about a day). With paid APIs, cost = tokens × the prices you set in `models.toml`, recorded per trial. Grading takes about 1 s per trial. Interrupted runs resume; `make regrade` re-scores saved replies without new API calls.

## 9. Threats to validity

- **Synthetic rules.** The rulebook is invented, so models cannot rely on memorised exchange behaviour. This measures careful spec-following in a financial domain more than prior domain knowledge.
- **A vs B is confounded.** B tasks are longer and touch more state, and F4/F5 have no A variant. H2 reports the difference as designed, not a pure coupling effect.
- **Output format.** Replies that do not contain the required file block score 0 and are counted separately (`FORMAT_ERROR`, `MISSING_FILE`) so formatting failures are not mistaken for reasoning failures.
- **Checkpoint provenance.** All 87 T2 checkpoint values come from the reference engine (`source = "engine"`). Some are hand-checked from engine pre-states in the author's audit worksheets (not in the ZIP); a fully independent hand derivation is not complete (see `CHANGELOG.md`). The clean-room reference passing every checkpoint is the main independent check.
- **Sampling.** 3 trials per task and model and 20 hidden seeds; CIs are reported and should be read as wide.
- **Unequal token budget for one model.** `mistral_large` ran with `max_tokens=8000` on `f1_fee_a`, `f1_fee_b`, `f2_replace_a`, `f2_replace_b`, `f3_fix_a`, `f5_basket_b` and two of three `f4_waterfall_b` trials, and with 16000 on `f3_fix_b`, one `f4_waterfall_b` trial, `f6_match_b`, `f7_funding_b`, `f8_adl_b` and all F9 tasks. The budget was raised after one truncated reply on an early task; the trials already run were not repeated. Every other model used one budget throughout (the value in the results table). Truncated replies (`OUTPUT_TRUNCATED`) are reported separately in the failure review, and `mistral_large` had one.
- **Free-tier models.** Free endpoints can change the model behind an ID without notice. Every trial records the model ID the provider reported serving and the run date; results describe those exact versions.
- **One author.** Domain review is by the author (`EXPERT_REVIEW.md`); a blinded human audit of grader verdicts on model outputs (`tools/human_audit.py`, Cohen's κ) is the author's own step and its result is reported in section 5 once it is done; until then the entry has no human-agreement number.

## 10. Provenance and AI use

- Built from scratch for the micro1 Eval Hackathon (Oct 30 – Nov 9, 2026). The rulebook, invariants, engine, tasks, mutants, graders and harness were written during the event.
- Ideas borrowed, not copied: deterministic simulation testing (FoundationDB, TigerBeetle); a task layout of instruction, tests and reference solution like the Harbor format described in the hackathon guide. No tasks are taken from an existing benchmark.
- AI tools drafted code, tests and documents, and an isolated agent wrote the clean-room reference. The author reviewed each task, reference answer and grading rule. Full detail, including the removed simulated results: [`AI_USE.md`](AI_USE.md).

### Prior work and sources

- **Deterministic simulation testing** (seeded, replayable simulations checked against invariants): the approach used by FoundationDB and TigerBeetle for databases and ledgers. The idea is borrowed; no code is.
- **Task layout** of instruction, public tests and reference solution follows the Harbor format described in the hackathon material.
- **FIX session semantics** (sequence numbers, duplicates, gap handling) are modelled in simplified, invented form for F3.
- **No existing benchmark or dataset was used.** The rulebook, engine, tasks, mutants, graders and harness were written during the event. Model outputs are from the providers' free tiers on the dates in the results tables.

## 11. Repository layout

```
tasks/<id>/            instruction.md, task.toml, public_tests/, tier2_trace.json
exchange_core/         the engine the model's file plugs into
reference/             reference solutions        reference_alt_v2/  clean-room second reference
mutants/<id>/<bug>/    81 hand-written bugs + expected grader verdicts
graders/               3-tier grader, trace generator, import policy, sandbox
harness/               run_eval.py (single-turn, feedback loop), adapters, stats, report
tools/                 validation, mutant tiers, transcript export, packaging, secrets scan
results/               run outputs (raw prompt/reply/score per trial) and summaries
transcripts/           representative transcripts exported from results/
```
