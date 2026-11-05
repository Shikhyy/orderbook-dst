# OrderBook-DST

**Can a model write exchange-core code that stays correct across hundreds of events, not just on the tests it can see?**

OrderBook-DST gives a model one file of a working exchange engine to implement (fee settlement, cancel/replace, FIX session handling, a liquidation waterfall, or atomic baskets), with a written rulebook and visible unit tests. The grader then replays 20 hidden, seeded 200-event simulations against a reference engine and checks four conservation invariants after every event: the deterministic-simulation-testing (DST) approach used for databases and ledgers.

> **Status.** The eval, graders and grader validation are complete and reproducible (see §4).
> Model results are pending: an earlier draft contained simulated results that did not come
> from any model; they were removed (see [`AI_USE.md`](AI_USE.md)). Every result reported
> here will come from `harness/run_eval.py` calling real provider APIs, with all transcripts
> in `results/`.

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

11 tasks in 8 families. Families F1–F3 have an isolated rule function (**A**) and an engine handler that must also update the surrounding state (**B**). Everything the grader checks is stated in the task's instruction and in [`docs/04_RULEBOOK.md`](docs/04_RULEBOOK.md).

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

All data is synthetic: the rulebook, accounts and event traces are generated for this benchmark.

## 4. Grading and grader validation

`graders/dst_grader.py` scores every attempt with code, not an LLM judge:

**score = 0.2 · T1 + 0.3 · T2 + 0.5 · T3**, pass = score 1.0

- **T1, visible tests** (in the prompt): the public pytest file for the task.
- **T2, checkpoints** (hidden): 87 targeted multi-step scenarios across the 11 tasks (exact tie rounding, partial-fill replaces, gap closure, rollback).
- **T3, hidden simulation** : 20 seeded traces × 200 events. After each event the candidate engine must emit the same reports as the reference (D1) and satisfy I1 cash/position conservation, I2 margin locks match resting orders, I3 order IDs and priorities strictly increase, and I4 FIX replay with duplicates and gaps gives the same state.

Partial credit is built in (tier scores are fractions of tests, checkpoints and seeds passed). The grader checks the final behaviour of the code, not how it was written.

### How the grader was validated (run it: `make validate`, ~45 s)

| Check | Result |
|---|---|
| V1 Reference solution passes every tier, all 11 tasks, graded exactly as a model's answer (same import allowlist) | PASS |
| V2 Clean-room second reference (`reference_alt_v2/`, written without seeing `reference/`) passes, all 11 tasks, same rules | PASS |
| V3 All 75 hand-written bug mutants fail, each with the invariant its `expect.toml` predicts | PASS |
| V4 / V5 Empty stub and hard-coded-answer stub score near 0 (cannot game T3) | PASS |
| V6 Grading is deterministic (same code → same score) | PASS |
| V7 Every hidden trace exercises the task's code path ≥ 10 times | PASS |
| V8 Mutants trigger I1 and I2, not only report mismatches | PASS |

Also tested (`make test`, 476 tests): prompts never contain hidden seeds, checkpoint values or reference code; candidate imports are restricted to an allowlist; secrets never reach saved replies; report statistics are recomputed from raw records.

### Which tier catches which bug (`make mutant-tiers`, no API calls)

Running all 75 mutants through the grader ([`results/grader_analysis/mutant_tiers.md`](results/grader_analysis/mutant_tiers.md)):

- **54 / 75** fail at least one *visible* test; 17 more are caught first by the hidden checkpoints; **4** pass every visible test and every checkpoint and are caught only by the hidden simulation: `f2_replace_b/m_lock_uses_current_rate` (a one-token change, `state.margin_bps` for `order.margin_bps`, that fails all 20 seeds on I2; run `make demo` to see it) two in `f6_match_b` (`m_post_only_ignores_own`, 14 of 20 seeds; `m_stp_stops_matching`, 20 of 20) and one in `f7_funding_b` (`m_skips_negative_cash`: skipping funding for accounts whose cash is already negative).
- So for the bugs the author anticipated, the visible tests are already strong. The open question the model runs answer is whether **model** bugs look like these, or are the kind only long simulations reveal.
- The hidden simulation also compares the **whole final engine state** with the reference's (not only balances). This was added after the first real run: a model skipped a required state update (storing the new mark price) that no report, invariant or balance revealed, and still scored a perfect T3. `f4_waterfall_b/m_mark_price_not_stored` reproduces it and fails all 20 seeds.
- The grader compares reports before checking invariants, so a bug that breaks conservation *and* changes a report would be labelled D1. The grader now also records every invariant broken at each seed's first failing event; this does not change any score, but it is what the H5 analysis uses.

## 5. Results

*Pending real model runs.* `make report` writes `results/main/summary.md` with, per model: exact model ID and settings, trials per task, pass rate with a hierarchical-bootstrap 95% CI, pass@k, pass^k, mean score, T1/T2/T3, and cost; a per-task table; each trial's failure type; and the hypothesis metrics in §6. The README table will be copied from that file unchanged.

| Model (exact ID, settings) | Trials / task | Pass rate [95% CI] | pass^5 | Mean score | T1 | T2 | T3 | Cost / run |
|---|---|---|---|---|---|---|---|---|
| frontier model A | 5 | – | – | – | – | – | – | – |
| frontier model B | 5 | – | – | – | – | – | – | – |
| smaller / open model | 5 | – | – | – | – | – | – | – |

## 6. Pre-registered hypotheses

Written and committed (`3fea5fd`) before any model run; see [`HYPOTHESES.md`](HYPOTHESES.md). `harness/report.py` computes each one the same way for every model:

| | Prediction | Computed as |
|---|---|---|
| H1 | Visible-test score exceeds hidden-simulation score | Mean of per-trial T1 − T3, hierarchical bootstrap CI; trials with extraction errors excluded |
| H2 | Variant B is harder than Variant A | Per-family A − B pass rate and score over F1–F3, one-sided stratified permutation test (A and B are different tasks, so this is unpaired; B tasks are also bigger, so a gap is not attributable to coupling alone) |
| H3 | Invariant feedback lets a model repair a failed attempt | First vs final turn on the *same* trial (`--mode feedback_loop`), exact McNemar test |
| H4 | Frontier models break I1/I2 less than small models | Share of hidden seeds without each invariant violated |
| H5 | Most Variant B failures are missed side effects, not wrong core logic | Share of failing B seeds where a conservation invariant broke vs report mismatch only (an automatic proxy; checked against transcripts) |

## 7. Failure analysis

*To be written by the author from the real transcripts* (`make transcripts` exports, per model and task, the lowest-scoring failure, any near miss, and a pass, with the verbatim reply and the grader's first failure). For each failure: what the model did, why, and whether the grader was right.

## 8. Reproduce it

Requirements: Python 3.12 or newer (tested on 3.12 and 3.14), dependencies pinned in `requirements.txt`. No API key is needed for steps 1–3.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make test            # 476 tests, ~15 s
make validate        # grader validation V1-V8, ~45 s
make demo            # one bug that only the hidden simulation catches, ~3 s
make mutant-tiers    # which tier catches each of the 75 bugs, ~20 s
```

Clean environment with Docker:

```bash
docker build -t orderbook-dst . && docker run --rm orderbook-dst
```

Run models on **free tiers** (no payment method needed; `.env` and `models.toml` are git-ignored):

```bash
cp models.free.example.toml models.toml   # Gemini, NVIDIA NIM, Groq (+ optional Mistral, OpenRouter, Cerebras)
cp .env.example .env                      # add the free keys you created; never commit or paste them
set -a; source .env; set +a
make list-models                          # exact model IDs your keys can use -> put them in models.toml
make dry-run                              # calls per model, no API calls
make pilot                                # 1 trial per task: checks reply format, truncation, headroom
make watch                                # in a second terminal: live progress, current wait, ETA (make status = one snapshot)
make run                                  # 11 tasks x 3 trials per model -> results/main
#   (add ONLY=label1,label2 to run some models, e.g. while one provider is down)
make feedback TASKS=f1_fee_b,f2_replace_b,f3_fix_b,f4_waterfall_b,f5_basket_b TRIALS=3
make report transcripts                   # tables, sanity checks, representative transcripts
```

Every trial prints a counter line (`[12/40] ... ETA ~25m`), rate-limit waits and retries are announced instead of silent, and `make status` / `make watch` show progress from another terminal (reads `results/<run>/progress.json`). A provider that returns an empty reply (for example `finish_reason=tool_calls` with no tool offered) is asked again up to twice, and the retry count is stored in the trial record.

Free tiers have per-minute and per-day caps. Set `rpm` and `rpd` per model from your provider dashboard: the harness spaces calls, retries 429/5xx with backoff, and when a daily cap is reached it stops that model cleanly. Run the same command again after the reset and it resumes; a quota error is never recorded as a model failure. Prompts are about 5–7k tokens; the harness warns when a provider reports far fewer input tokens than the prompt has (a truncated prompt is not a task failure). Paid APIs work the same way with `models.example.toml`.

Optional reasoning-effort ablation (more effort should not score worse; if it does, suspect the task): `models.ablation.example.toml`.

**Cost and runtime.** Each call sends about 5.3k–6.6k input tokens; a single-turn run is 40 calls per model, a feedback run up to 4 calls per trial. On free tiers the cost is $0; the limit is the daily request cap (for example ~45 calls/day means one model's single-turn run takes about a day). With paid APIs, cost = tokens × the prices you set in `models.toml`, recorded per trial. Grading takes about 1 s per trial. Interrupted runs resume; `make regrade` re-scores saved replies without new API calls.

## 9. Threats to validity

- **Synthetic rules.** The rulebook is invented, so models cannot rely on memorised exchange behaviour. This measures careful spec-following in a financial domain more than prior domain knowledge.
- **A vs B is confounded.** B tasks are longer and touch more state, and F4/F5 have no A variant. H2 reports the difference as designed, not a pure coupling effect.
- **Output format.** Replies that do not contain the required file block score 0 and are counted separately (`FORMAT_ERROR`, `MISSING_FILE`) so formatting failures are not mistaken for reasoning failures.
- **Checkpoint provenance.** All 87 T2 checkpoint values come from the reference engine (`source = "engine"`). Some are hand-checked from engine pre-states in the author's audit worksheets (not in the ZIP); a fully independent hand derivation is not complete (see `CHANGELOG.md`). The clean-room reference passing every checkpoint is the main independent check.
- **Sampling.** 5 trials per task and 20 hidden seeds; CIs are reported and should be read as wide.
- **Free-tier models.** Free endpoints can change the model behind an ID without notice. Every trial records the model ID the provider reported serving and the run date; results describe those exact versions.
- **One author.** Domain review is by the author (`EXPERT_REVIEW.md`); a blinded human audit of grader verdicts on model outputs (`make audit`, Cohen's κ) runs once real trials exist.

## 10. Provenance and AI use

- Built from scratch for the micro1 Eval Hackathon (Oct 30 – Nov 9, 2026). The rulebook, invariants, engine, tasks, mutants, graders and harness were written during the event.
- Ideas borrowed, not copied: deterministic simulation testing (FoundationDB, TigerBeetle); a task layout of instruction, tests and reference solution like the Harbor format described in the hackathon guide. No tasks are taken from an existing benchmark.
- AI tools drafted code, tests and documents, and an isolated agent wrote the clean-room reference. The author reviewed each task, reference answer and grading rule. Full detail, including the removed simulated results: [`AI_USE.md`](AI_USE.md).

## 11. Repository layout

```
tasks/<id>/            instruction.md, task.toml, public_tests/, tier2_trace.json
exchange_core/         the engine the model's file plugs into
reference/             reference solutions        reference_alt_v2/  clean-room second reference
mutants/<id>/<bug>/    75 hand-written bugs + expected grader verdicts
graders/               3-tier grader, trace generator, import policy, sandbox
harness/               run_eval.py (single-turn, feedback loop), adapters, stats, report
tools/                 validation, mutant tiers, transcript export, packaging, secrets scan
results/               run outputs (raw prompt/reply/score per trial) and summaries
transcripts/           representative transcripts exported from results/
```
