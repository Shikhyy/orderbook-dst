# Fact sheet for the write-up (facts only; the reading and the wording are the author's)

Source of every number: `results/main/summary.md` and `results/feedback/summary.md`
(regenerate with `make report`), the trials in `results/main/trials.jsonl`, and
`docs/FAILURE_REVIEW.md`. Re-check any number you quote against those files. If the
data changes (a rerun, a regrade), this sheet is stale.

## 1. What was run
- 7 models, all on free tiers ($0.00): nemotron_ultra, mistral_large, gemini_35_flash,
  flash_lite, gemma_26b, nemotron_nano, ministral_8b. 3 trials per task and model,
  single turn.
- 17 tasks: 11 implementation tasks (F1 to F8, the "headline") and 6 diagnose-and-fix
  tasks (F9, reported separately). 329 main trials plus 30 feedback-loop trials.
- All stored scores were regraded with the current grader (commit e781834 or later).
  The first regrade after e781834 flipped one trial (nemotron_nano f8_adl_b trial 1,
  pass to fail); a second full regrade changed nothing, so the scores are repeatable.
- Incomplete: gemini_35_flash has 23 of 33 headline trials and 0 of 18 F9 trials (free
  Gemini tier rate limits, 429, after retries). It is missing all trials of f3_fix_b,
  f7_funding_b, f8_adl_b and one f6_match_b trial. Say this plainly.

## 2. Headline results (F1 to F8)
| model | pass rate | mean score |
|---|---|---|
| nemotron_ultra | 100.0% (33/33) | 1.000 |
| mistral_large | 93.9% | 0.960 |
| gemini_35_flash | 87.5% (incomplete) | 0.935 |
| gemma_26b | 81.8% | 0.846 |
| flash_lite | 78.8% | 0.861 |
| nemotron_nano | 36.4% | 0.420 |
| ministral_8b | 36.4% | 0.508 |

Pass = score 1.0 (all public tests, all checkpoints, all 20 hidden seeds).
Per-task pass counts over all models (headline, trials that exist): f1_fee_a 21/21,
f2_replace_a 20/21, f3_fix_a 20/21, f3_fix_b 15/18, f1_fee_b 14/21, f4_waterfall_b 14/21,
f2_replace_b 13/21, f7_funding_b 12/18, f8_adl_b 12/18, f6_match_b 11/20,
f5_basket_b 9/21. The hardest task was f5_basket_b (all-or-nothing rollback).

**The top-end limitation (state it, do not hide it):** nemotron_ultra passed every
trial it ran (51/51 including F9), and mistral_large failed only 2 of 51. Four task
designs were tried specifically to break the strongest model (F6, F7, F8, F9) and none
did. On these free models, a strong model can implement and debug this engine from a
clear specification. The benchmark separates the small and mid models, not the top.
Also: no closed frontier model (for example from OpenAI or Anthropic) was run, because
the project used free tiers only, so nothing here says how those models would do.

## 3. What the failures were (headline, 221 trials)
161 passed. The 60 failures:
- 32 wrong behaviour (code ran, results wrong)
- 16 code crashed in a tier (for example calling attributes that do not exist, such as
  `Engine.orders`, `Engine.accounts`, `Engine.book`)
- 12 output truncated at the shared token limit, so no code to grade

Truncation (12, 11 of them nemotron_nano) is a token-budget effect, not a logic result.
Report it separately from the logic failures.

Failures that read as real model limitations (see `docs/FAILURE_REVIEW.md` for each):
- f5_basket_b: no all-or-nothing rollback (emits per-leg reports instead of a rollback);
  gemini_35_flash treats any CANCELLED report as a failed leg (3 of 3 trials).
- f6_match_b: best-price selection bug (gemma), filled order kept on the book, wrong
  leaves, sort and self-trade-prevention errors (ministral).
- f7_funding_b: 2 units of money lost to rounding (nemotron_nano).
- f1/f2 (B): invented engine attributes (nemotron_nano).

## 4. Task and grader defects found and fixed (use these for the review and insight points)
These are defects in our own work that careful checking found. Each one invalidated or
changed results, and each was fixed and rerun or regraded.
1. An earlier simulated-results analysis was withdrawn (see `AI_USE.md`). All numbers
   now come from real model runs.
2. F3 spec gap: the first `epoch` value and lazy session creation were not stated, which
   caused crashes (`KeyError`). Fixed, reran.
3. Unequal token budget for mistral_large (8000 vs 16000). Raised, reran one trial. The
   final data still mixes budgets for mistral_large (8000 for most tasks, 16000 for F6 and
   F7 and one rerun). State this in the method notes.
4. F7 R-Y4 wording was ambiguous (my defect): it made 4 of 5 failures spurious. Reworded,
   discarded 12 trials, reran.
5. F3 `body=None` rule was not in the instruction (the reference skipped dispatch, and 7
   public tests relied on it). Added to R-S9, reran all f3_fix_b trials.
6. Four wrong implementations scored 1.0 on every tier (a grader gap, commit e781834):
   f8 vault draw without a floor, f8 zero-share ADL report, f4 and f9_dbg_2 strict
   inequality in the stage-1 re-test, f7 and f9_dbg_5 vault floored at 0. Checkpoints and
   mutants added (81 mutants total). One stored trial flipped from pass to fail.
7. Two early f8 checkpoint designs could not distinguish wrong implementations. Fixed.
8. The audit tool had defects: `--export-sheet` failed without a path, the sample
   included trials with no code, and a key could be overwritten. Fixed.
9. The review packet's F7 hand-check example was wrong (a transfer, not a residual).
   Replaced and checked on the reference engine.

## 5. Hypotheses: what the computed numbers say (the prediction vs the data)
Pre-registered in `HYPOTHESES.md` before any run. The computed values are in
`results/main/summary.md`. Plain statements, with the caveats that apply:
- **H1 (visible-test score exceeds hidden-simulation score).** T1 minus T3 per model:
  ministral_8b 0.504 [0.26, 0.74] and flash_lite 0.143 [0.02, 0.31] have intervals that
  exclude 0. nemotron_ultra is 0.000. For the other models the interval includes 0.
  So the visible tests overstate quality for the weaker models, and not for the best.
- **H2 (Variant B harder than Variant A).** One-sided permutation test over F1 to F3:
  nemotron_nano A minus B = 0.667 (p = 0.009), ministral_8b 0.667 (p = 0.005),
  gemma_26b 0.333 (p = 0.053). nemotron_ultra, mistral_large and gemini_35_flash show no
  gap (ceiling). Caveat: A and B are different tasks and B tasks are larger, so the gap
  is not attributable to coupling alone. Only three families have both variants.
- **H3 (invariant feedback lets a model repair a failed attempt).** 30 trials: gemma_26b
  60.0% to 100.0%, 6 fixed and 0 broken, McNemar p = 0.031; flash_lite 60.0% to 93.3%,
  5 fixed and 0 broken, p = 0.062. Only two models and five tasks were run.
- **H4 (stronger models break the conservation and margin invariants less).** I1 / I2
  seed survival: ministral_8b 0.81 / 0.90, nemotron_nano 0.94 / 1.00, flash_lite
  0.97 / 1.00; nemotron_ultra, mistral_large, gemma_26b, gemini_35_flash 1.00 / 1.00.
  The direction holds, driven mostly by ministral_8b.
- **H5 (most Variant B failures are missed side effects, not wrong core logic).** The
  automatic proxy (share of failing seeds where a conservation law broke) is 33%
  (gemma_26b), 20% (flash_lite), 32% (nemotron_nano), 67% (ministral_8b), 0% (gemini).
  By that proxy H5 is not supported for most models. The proxy is automatic and must be
  checked against transcripts; do not state H5 as confirmed or refuted without that.

## 6. F9 (diagnose and fix), exploratory
Not in the headline or in H1 to H5 (Amendment A3). The strong models pass nearly all of
it (nemotron_ultra, mistral_large and flash_lite 100%); weaker models are lower
(ministral_8b weakest). Per task: f9_dbg_6 passed most, f9_dbg_3 least. f9_dbg_5 leaks a
hint (an unused `residual` variable and a skipped comment) and looks like a reading task.
Honest reading: finding a one-line defect from a symptom, with the full spec in hand, was
not harder than implementing for the strong models.

## 7. Limitations to state in the write-up
- One author, with the task and reference code drafted largely by an AI assistant (see
  `AI_USE.md`); the independent checks are the clean-room second reference, the mutants
  and your own review.
- Free models only; no closed frontier models; gemini_35_flash incomplete.
- Checkpoint values come from the reference engine (`source = "engine"`); the clean-room
  reference passing every checkpoint is the main independent check.
- Three trials per task and model, so confidence intervals are wide.
- The saturation at the top, as above.
- F6 relies on an implied rule (a later margin-rate change does not alter existing
  orders), accepted as implied; only the hidden seeds catch the matching bug.
- The blinded human audit and the F6 to F9 sign-offs are yours; until they are done the
  entry has no human-agreement number.

## 8. A talk track for the video (draft; rewrite in your own voice, 5 minutes or less)
1. (0:30) The problem: coding models are judged on tasks that either leak the answer or
   cannot be checked. Here the check is a hidden, seeded simulation that replays an
   exchange engine and compares to a reference, so a wrong implementation is caught by a
   broken rule, not a guess.
2. (1:00) How it is built: 17 tasks, a 3-tier grader (public tests, hidden checkpoints,
   20 hidden seeds), 81 hand-written bugs that the grader must catch, a clean-room second
   reference.
3. (2:00) Results: show the headline table, the saturation at the top, and one real
   failing transcript (for example f5_basket_b: no all-or-nothing rollback) from
   `transcripts/`.
4. (1:00) What I found about my own work: the defects in section 4, and what the
   feedback loop result means.
5. (0:30) Limits and what a next version needs (a harder task the strongest model fails).
