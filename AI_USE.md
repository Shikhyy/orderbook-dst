# AI use

The author designed the benchmark, reviewed every task, reference answer and grading rule, and made every audit verdict. AI tools did the following.

| Step | Tool | Use |
|---|---|---|
| Scaffold, engine, tasks, tests, documents | Antigravity (Claude Sonnet 4.6 thinking), then Claude Code (Claude Sonnet 5.5) | Code generation, test writing, document drafting |
| Clean-room reference (`reference_alt_v2/`) | An isolated agent that never saw `reference/` | Independent second implementation used to validate the grader |
| `EXPERT_REVIEW.md` sections 9 to 12 | Antigravity (Claude Sonnet 4.6 thinking) | Original draft; the author re-wrote it, keeping only claims they verified |
| Audit cross-check | Claude Code (Claude Sonnet 5.5) | Read two audited trials and the grader output and found the T05 error. It chose no verdict |
| Claude Sonnet reference run | Claude Sonnet subagents in Claude Code | Acted as a candidate model on 6 trials (`f5_basket_b`, `f6_match_b`), given only the harness prompt and graded by the normal grader. Reported separately |
| README sections on failure analysis, hypotheses and prior work | Claude Code (Claude Sonnet 5.5) | Drafted from `docs/FAILURE_REVIEW.md` and the result summaries |
| Video | Piper text-to-speech (`en_US-lessac-medium`), Chrome, ffmpeg | Synthetic narration over frames rendered from real command output and result files |

## Review steps

1. The author reads each file the agent creates before it is committed.
2. The author runs `make test` and `make validate` after each milestone.
3. The author checks each claim in the failure analysis against the result files.
4. The author checks this file against the submission requirements before upload.

## What the agents did not do

- They did not change a rule to lower or raise a model pass rate.
- The model results come only from `harness/run_eval.py` calling real provider APIs (the six Sonnet trials are labelled and reported separately).

## Correction: simulated results removed

An earlier draft of this repository (commits `710420a`, `f733c6c`, `038bd25`) contained result files that were not real model output. A local script, `scratch/generate_benchmark_results.py`, chose the reference solution, the alternative reference or a mutant for each "trial" from a hand-written schedule and filled in latency and token counts with random numbers; `scratch/run_feedback_trials.py` did the same for the feedback-loop results. All of those files and every number taken from them were removed. The only results this submission reports come from real provider APIs, with each trial's prompt, raw reply, extracted files and score saved under `results/`.
