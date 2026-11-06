# Review packet: F6/F7 sign-off and the blinded human audit

Purpose: everything the author needs to (A) review and sign off `f6_match_b` and
`f7_funding_b`, and (B) do the blinded human audit. Both are the author's own
judgement. The assistant drafted F6 and F7, so a review by the author is the
independent check. Do not sign anything you have not checked yourself.

## A. Sign-off for f6_match_b and f7_funding_b

### What "sign-off" changes
1. In `tasks/<id>/task.toml`: set `author_signoff = true`.
2. Rewrite `difficulty_reason` in your own words (the current text is the assistant's).
3. In `EXPERT_REVIEW.md` sections 9 and 10: replace "Author Audit: PENDING" with your
   own domain rationale (compare section 8, f5_basket_b, for the expected depth).
4. `make preflight` flags any task whose `author_signoff` is false.

### How to review (about 45 min per task)
Read in this order: `tasks/<id>/instruction.md`, the rule section in `docs/04_RULEBOOK.md`,
`reference/<id>/*.py`, then `tasks/<id>/public_tests/`. Ask, for every rule:
- Is it unambiguous? Could a careful engineer read it two ways?
- Does the reference do exactly what the text says, nothing more?
- Is anything the reference does not written down in the instruction?
  (This is how three defects slipped in earlier: F3 epoch start, F3 `body=None`, F7 R-Y4.)

### f6_match_b: NEW_LIMIT handler (rules R-B3, R-B4, R-B5, R-M1 to R-M5)
Target: `exchange_core/handlers/new_limit.py`. Task: implement validation, matching,
self-trade prevention (STP), lock bookkeeping, IOC and resting remainder.

Points to check by hand:
1. **R-B4 order.** Validation order is unknown account, invalid order, post-only cross,
   margin. A rejected order uses no counter value. Do you agree this is the natural
   order, and is "would match now" clear when the only crossing order is the account's own?
2. **R-M3 STP.** The resting own-account order is cancelled with reason STP, its lock is
   released, and matching continues. Is "continues" clear (it must not stop the sweep)?
3. **R-M4 step 4 / R-M5.** The lock is recomputed per fill with `ceil_div`, and fully
   filled orders release the whole lock. Check one example by hand (below).
4. **R-B5 step 2. DECIDED (Nov 6): accepted as implied, no F6 rerun.** The order stores the engine's current
   `margin_bps` at entry, and R-M4 says "using the margin_bps stored in that order". That
   implies a later `SET_MARGIN_RATE` does not change an existing order's lock, but the
   instruction never says so in one sentence. `m_relock_current_rate` is a plausible
   misreading, and `tests/test_worked_examples.py::test_r_g1_margin_rate_worked_example`
   confirms the intended behaviour. Either (a) add a sentence to
   `tasks/f6_match_b/instruction.md`, e.g. "A later SET_MARGIN_RATE does not change the
   margin_bps or lock of an existing order; only new orders use the new rate", **which
   changes the prompt and means every F6 trial must be rerun on the new wording** (21
   trials, as for F3 and F7), or (b) consciously accept it as implied and say so in your
   sign-off notes. The author chose (b): the instruction is left unchanged, and the sign-off notes for F6 should say that a later `SET_MARGIN_RATE` not altering existing orders is implied by R-B5 step 2 and R-M4 step 4, not stated in one sentence, and that `m_relock_current_rate` (caught only by the hidden seeds) is the matching bug. Do not sign F6 as "no ambiguity".
5. **Fills at the resting price** (R-M2), and a fill can drive `free_cash` negative.

Hand-check example (do this yourself, then compare with the reference). Default
`margin_bps` is 2000. A resting SELL 10 @ 100,000,000 (account A1) and an incoming
BUY 4 @ 101,000,000 (account A2):
- initial locks: seller 10 x 100,000,000 x 2000 / 10000 = 200,000,000; buyer
  4 x 101,000,000 x 2000 / 10000 = 80,800,000
- the fill is 4 @ 100,000,000 (the resting price)
- seller has 6 left: new lock 6 x 100,000,000 x 2000 / 10000 = 120,000,000, so 80,000,000
  is released; buyer has 0 left: new lock 0, so all 80,800,000 is released
- A1 and A2 start with 5,000,000,000 each. The buyer pays 400,000,000 plus a taker fee of
  1,100,000; the seller receives 400,000,000 plus a rebate of 100,000; the vault gains
  1,000,000. Final: A1 free cash 5,280,100,000 and lock 120,000,000; A2 free cash
  4,598,900,000 and lock 0.
(I ran this on the reference engine and the numbers match.)

Mutants (all 11 are expected to be caught): `m_fill_at_taker_price`,
`m_filled_taker_rests`, `m_ioc_lock_kept`, `m_maker_lock_stale`, `m_margin_default_rate`,
`m_no_stp`, `m_post_only_ignores_own`, `m_relock_current_rate`, `m_stp_ignores_price`,
`m_stp_lock_not_released`, `m_stp_stops_matching`. Check that each is a plausible real
bug and not a contrived one.

Known failures to sanity-check against the spec: gemma best-price bug, filled order
stored, ministral leaves/sort/STP errors (see `docs/FAILURE_REVIEW.md`). Confirm each is
a model error and not something the instruction hides.

### f7_funding_b: FUNDING handler (rules R-Y1 to R-Y5)
Target: `exchange_core/handlers/funding.py`. Task: clamp the rate, move funding between
longs and shorts with per-account rounding, route the rounding residual to `fee_vault`,
report `FUNDING_APPLIED`, then always run the margin waterfall.

Points to check by hand:
1. **R-Y1 clamp** to [-3000, +3000] ppm, limits included. Field is ppm, not bps. Is that
   clear (the field is named `bps`)?
2. **R-Y2 direction.** Pays if long and rate > 0, or short and rate < 0. Otherwise receives.
   LIQ is included. `free_cash` may go negative. Locks and volume do not change.
3. **Rounding.** Half-even, applied to the non-negative amount before the sign is applied.
4. **R-Y3.** Net payments (payments minus receipts, may be negative) go to `fee_vault`, so
   total cash plus vault is unchanged. The vault is not floored at 0
   (`m_vault_floor_zero` is the matching bug).
5. **R-Y4.** `qty` counts every processed account including one that rounds to 0, and is 0
   when `rate == 0`. This wording was ambiguous once and was reworded. Re-read it
   critically.
6. **R-Y5.** The waterfall always runs, even at rate 0, at the current mark.

Hand-check examples (an earlier version of this example was wrong: a long that pays
1,000,000 against a short that receives 400,000 is a transfer to the other short, not a
rounding residual. In a closed state the position sum is 0, so a clean example needs
three accounts):
- Residual: mark 500,000, rate 1 ppm, positions +3, -1, -2. Amounts are
  round_half_even(1,500,000 x 1, 1,000,000) = 2, round_half_even(500,000 x 1, 1,000,000)
  = 0, round_half_even(1,000,000 x 1, 1,000,000) = 1. The long pays 2; the shorts receive
  0 and 1. The residual +1 goes to `fee_vault`, so cash plus vault is unchanged. (I ran
  this on the reference engine: long -2, shorts 0 and +1, vault +1.)
- Half-even, in integers: round_half_even(2_500_000, 1_000_000) = 2 and
  round_half_even(3_500_000, 1_000_000) = 4. Half-up gives 3 and 4, which is what
  `m_half_up_rounding` does.

Mutants (all 12 expected to be caught): `m_floor_rounding`, `m_half_up_rounding`,
`m_no_clamp`, `m_no_waterfall`, `m_qty_skips_zero_amount`, `m_residual_not_to_vault`, `m_sign_swapped`,
`m_skips_liq`, `m_skips_negative_cash`, `m_vault_floor_zero`, `m_waterfall_only_if_rate`,
`m_wrong_mark_in_waterfall`.

### Sign-off checklist (tick only what you verified)
- [ ] I read the instruction and found no ambiguity (or fixed it and logged it).
- [ ] I reproduced the hand-check examples above.
- [ ] I read the reference and it matches the rules.
- [ ] The mutants are realistic bugs.
- [ ] Each failure in `docs/FAILURE_REVIEW.md` is correctly labelled. Most are model errors,
      but some are task defects that were found, fixed and rerun (F3 epoch start, F3
      `body=None`, F7 R-Y4 wording). For F7, check that the affected trials were discarded
      and rerun on the corrected wording.
- [ ] I rewrote `difficulty_reason` and the `EXPERT_REVIEW.md` section in my own words.

## B. Blinded human audit

### What it measures
Do your judgements of model code agree with the grader's pass/fail? The tool reports a
2x2 agreement table and Cohen's kappa. This is the evidence for "grader reliability"
and "human review". It only counts if the judgements are yours and made blind.

### Do it after the data is final (three steps, in this order)
1. **Freeze the tree.** `git status` must be clean and no `make run`, `make feedback` or
   `make regrade` may be running. Graders, traces and mutants have changed after trials
   were scored (commit e781834 closed four false passes), so the stored scores must be
   regenerated first.
2. **Regrade the stored trials with the current grader**: `make regrade`. Then check
   `results/main/run_meta.json` records the commit you are on. The audit sample is
   stratified on the grader's pass/fail, so exporting before the regrade would sample on
   stale verdicts.
3. **Draw the sample once** (below). The sample comes from `results/main/trials.jsonl`.
   Re-drawing after seeing results defeats the blinding, so the tool now refuses to
   overwrite an existing `results/audit_key.json` unless you pass `--force`.

### Steps
```bash
.venv/bin/python tools/human_audit.py --export-sheet
```
(`--export-sheet` takes an optional path and defaults to `results/audit_sheet.md`.)
This writes `results/audit_sheet.md` (trial ids T01 to T20 with the full code; model and
grader outcome hidden) and `results/audit_key.json` (the answer key; do not open it
before you finish; copy it somewhere safe after export). Sample: 10 passing and 10
failing trials, fixed seed 42.

What the sample excludes, and why:
- Trials with no code to read (`OUTPUT_TRUNCATED`, `FORMAT_ERROR`, or no Python file). A
  human cannot judge them, and calling them "incorrect" would trivially agree with the
  grader and inflate kappa. Report how many such trials exist separately.
- The F9 diagnose-and-fix tasks, so the audit supports the headline F1 to F8 benchmark.
  Pass `--include-f9` only if you want them in, and then report them as their own stratum.

For each trial, decide: **does this code correctly implement the task's instruction?**
Judge against `instruction.md` and the rulebook, not against what you guess the grader
did. Mark correct or incorrect and write one line of reason. Save the verdicts as JSON
with **all 20 keys present** (a missing key makes the tool fall back to an interactive
prompt and can hang or produce a short sample):

```json
{
  "T01": {"verdict": true,  "reason": "matches R-M3, STP continues sweep"},
  "T02": {"verdict": false, "reason": "stops matching after STP"}
}
```
`verdict: true` means you judge it correct.

```bash
.venv/bin/python tools/human_audit.py --verdicts-json results/my_verdicts.json
```
Output: `results/human_audit.md` with the agreement matrix and kappa.

### Rules for a valid audit
- Never use `--auto-agree`. It copies the grader's verdict as yours and produces a
  meaningless kappa of 1.0. It exists only for testing the tool.
- Do not open `audit_key.json` or the grader results until all 20 verdicts are written.
- Disagreements are the valuable part. Do not change a verdict to match the grader.
  For each disagreement, decide whether the grader or your reading is wrong, and write
  it down. A grader false pass or false fail is a finding to fix and report.
- Expect about 2 to 4 hours for 20 trials.

### What to report afterwards
Put it in a new named subsection of `README.md` section 5 (for example "5.x Blinded
human audit"), not in section 7 (failure analysis), and in `EXPERT_REVIEW.md`. Include:
- raw agreement (a count out of 20) next to kappa. The sample is deliberately balanced
  10 pass and 10 fail, so kappa is not a population statistic; say so.
- the sample size caveat: with 20 trials the confidence interval on kappa is wide.
- each disagreement with your reasoning and what you changed, if anything.
- how many trials were excluded as not judgeable, by cause.

## C. Sign-off for f8_adl_b and the six F9 tasks (added later)

Same rules as section A: read, reproduce by hand, then sign. In `tasks/<id>/task.toml` set `author_signoff = true`, rewrite `difficulty_reason` in your own words and replace PENDING in `EXPERT_REVIEW.md` (section 11 is f8_adl_b; section 12 covers all six F9 tasks).

### f8_adl_b (rules R-L1 to R-L5, `docs/04_RULEBOOK.md` section 10c)
Check by hand: the deficit is `max(0, -free_cash)` after liquidation; the vault draw is capped by a non-negative vault; shares are floor divisions, leftover units go to the largest weights and then by ascending string order of the account id (`A10` before `A2`); `LIQ` and the ruined account are never charged; the report order is `LIQUIDATED` (emitted by the caller, not by `handle_bankruptcy`), then `INSURANCE_DRAWN` (if any), then all `ADL_APPLIED` in ascending id order, or `BAD_DEBT` if no account is eligible, never both (R-L5); money is conserved exactly. Take one small example with two equal weights and a leftover of 1 and compute it yourself. Ask whether the instruction, not only the reference, states every convention (it is the task with the longest chain of small conventions).

Open points from the independent review (Nov 6), for your sign-off notes. The three grader gaps behind them are closed (see `CHANGELOG.md`); these are wording and design points that are yours to decide:
- `pre_position == 0` is not defined in R-L3 (the reference treats it as short). The engine never calls the procedure with 0, so it cannot happen, but the instruction could say `pre_position != 0`.
- The instruction's R-L5 adds "Positions, locks and volumes do not change"; the rulebook's R-L5 does not. They agree in substance.
- "neither `LIQ` nor X" in R-L3: the X part never matters, because X has position 0 after the liquidation and the zero-position clause already excludes it.
- The reference docstring says "Rules R-L1 to R-L4"; the task covers R-L5 as well.
- Mutants of f8_adl_b now include `m_vault_not_floored` and `m_zero_share_reported` (21 in total).

### F9: diagnose and fix (`f9_dbg_1` to `f9_dbg_6`)
Each task = specification of an existing task + bug report + the handler with one defect; graded like that task. What to review for each:
1. **The bug is real and single.** Open `tasks/<id>/buggy/<path>` and compare with `reference/<base task>/<file>`. The difference should be one defect only (the lines are listed in `docs/F9_INSTANCES.md`).
2. **The symptom is honest.** Read `tasks/<id>/symptom.md`. Re-run the trace by hand for the first events if you can; the numbers come from the reference engine, not from the fix.
3. **The prompt does not give the answer away.** Read the whole prompt (`python -c "from harness.prompt import build_prompt_for_task as b; print(b('f9_dbg_5').user_prompt)"`). Look for comments, names or stale text that point at the fix. Known hints: in `f9_dbg_5` the variable `residual` is computed and never used, and the buggy file's rule comments go R-Y1, R-Y2 and then skip to R-Y4, so the missing R-Y3 block is conspicuous. With its high pass rate, `f9_dbg_5` looks like a reading task, not a diagnosis task. Either ask for the hint to be removed (which changes the prompt, so rerun that task) or accept it as an easy task and say so.
4. **The fix is unique.** Is there more than one behaviour a careful engineer could defend? The grader accepts exactly the reference behaviour, so a second defensible reading would make a correct answer fail.
5. **The difficulty is real.** Decide for each task whether you would call it a diagnosis task or just a reading task. Trials now exist (see the README F9 table; read the numbers there, they change if the run is resumed). F9 is not uniformly hard: on the data as of Nov 6, f9_dbg_6 passed 15/15 and f9_dbg_5 14/15 while f9_dbg_3 passed 10/18. Do not call F9 hard overall.
