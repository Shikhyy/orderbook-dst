# AI Use

## Tools used

| Step | Tool | Version | Use |
|---|---|---|---|
| Scaffold to M11 | Antigravity (Claude Sonnet 4.6 thinking) | 2026-11-01 | Code generation, test writing, document drafting |
| EXPERT_REVIEW.md sections 9-12 (original draft) | Antigravity (Claude Sonnet 4.6 thinking) | 2026-11-07 | AI drafted original text; human re-wrote in their own words, keeping only verified claims (reference-engine hand examples checked, R-B3 omission noted, F9 defect-symptom mappings confirmed from task diffs) |
| Audit cross-check (2026-11-07) | Claude Code (Claude Sonnet 5.5) | 2026-11-07 | Read trials T09 and T05 and the grader output to check the reviewer's verdicts; found the T05 error. Also corrected README, HYPOTHESES and EXPERT_REVIEW wording. Did not choose any verdict. |
| Claude Sonnet reference run (2026-11-07) | Claude Sonnet via Claude Code subagents | 2026-11-07 | Acted as a candidate model on 6 trials (f5_basket_b, f6_match_b), given only the harness prompt; graded by the normal grader. Reported separately in the README. |

## Review steps

1. The author reads each file the agent creates before the commit.
2. The author runs `make test` and `make validate` after each milestone.
3. The author reads the failure cards and checks each claim against result files.
4. The author checks `AI_USE.md` against the submission requirements before upload.

## What the agent did not do

- The agent did not run model API calls.
- The agent did not change a rule to lower or raise a model pass rate.

## Correction: simulated results removed

An earlier draft of this repository (commits `710420a`, `f733c6c`, `038bd25`)
contained result files that were not real model output. A local script,
`scratch/generate_benchmark_results.py`, picked the reference solution, the
alt reference or a mutant for each "trial" from a hand-written schedule and
filled latency and token counts with random numbers.
`scratch/run_feedback_trials.py` did the same for the feedback-loop results.
The earlier statement here that no result files were invented was wrong.

All of those files (`results/`, `transcripts/`) and every number taken from
them in the README, `HYPOTHESES.md`, `SUBMISSION_DESCRIPTION.md` and
`VIDEO_SCRIPT.md` have been removed. The only results this submission reports
come from `harness/run_eval.py` calling real provider APIs, with each trial's
prompt, raw reply, extracted files and score saved under `results/`.
