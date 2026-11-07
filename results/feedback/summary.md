# OrderBook-DST Evaluation Summary

- Run date (UTC): 2026-11-06T07:08:57.325595+00:00
- Git SHA: `c07d5a4ca1124aa3bdcaa68380382226f39ef4db`
- Total trials: 30

## Headline results

| Model (ID, settings) | Trials / task | Pass rate | 95% CI | pass@k | pass^k | Mean score | 95% CI | T1 | T2 | T3 | Cost (run) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **gemma_26b** (`gemma-4-26b-a4b-it`, max_tokens=8000, api_key_env=GEMINI_API_KEY) | 3 | 100.0% | [1.00, 1.00] | 100.0% | 100.0% | 1.000 | [1.00, 1.00] | 1.00 | 1.00 | 1.00 | $0.00 |
| **flash_lite** (`gemini-3.1-flash-lite`, max_tokens=8000, api_key_env=GEMINI_API_KEY) | 3 | 93.3% | [0.73, 1.00] | 100.0% | 80.0% | 0.983 | [0.93, 1.00] | 1.00 | 0.98 | 0.98 | $0.00 |

Pass = score 1.0 (all public tests, all checkpoints and all 20 hidden seeds). pass@k: at least one of k trials passes; pass^k: all k pass. CIs are a hierarchical bootstrap over tasks, then trials. Cost uses the per-model prices in `models.toml` (0 if not set).

## Per-task results (passes / trials, mean score)

| Task | gemma_26b | flash_lite |
|---|---|---|
| `f1_fee_b` | 3/3 (1.00) | 3/3 (1.00) |
| `f2_replace_b` | 3/3 (1.00) | 3/3 (1.00) |
| `f4_waterfall_b` | 3/3 (1.00) | 2/3 (0.92) |
| `f5_basket_b` | 3/3 (1.00) | 3/3 (1.00) |
| `f6_match_b` | 3/3 (1.00) | 3/3 (1.00) |

## Outcome of each trial by task

First failure per trial: invariant ID (I1–I4), D1 = report/state differs from reference, T1/T2 = failed visible tests or checkpoints, or an extraction/import error.

**gemma_26b**

- `f1_fee_b`: pass×3
- `f2_replace_b`: pass×3
- `f4_waterfall_b`: pass×3
- `f5_basket_b`: pass×3
- `f6_match_b`: pass×3

**flash_lite**

- `f1_fee_b`: pass×3
- `f2_replace_b`: pass×3
- `f4_waterfall_b`: D1×1, pass×2
- `f5_basket_b`: pass×3
- `f6_match_b`: pass×3

## Sanity checks

- ⚠️ Little headroom: gemma_26b passes 100% of trials. The eval may no longer show a limitation for this model.
- ⚠️ `f1_fee_b` is passed by every trial of every model: it does not separate models.
- ⚠️ `f2_replace_b` is passed by every trial of every model: it does not separate models.
- ⚠️ `f5_basket_b` is passed by every trial of every model: it does not separate models.
- ⚠️ `f6_match_b` is passed by every trial of every model: it does not separate models.

## Pre-registered hypotheses (computed; see HYPOTHESES.md)

| Model | H1: T1 − T3 [95% CI] | H2: A − B pass rate (p) | H2: A − B score (p) | H4: I1 / I2 seed survival | H5: conservation share of B failing seeds |
|---|---|---|---|---|---|
| gemma_26b | 0.000 [0.00, 0.00] | – (p=–) | – (p=–) | 1.00 / 1.00 | – of 0 |
| flash_lite | 0.023 [0.00, 0.09] | – (p=–) | – (p=–) | 1.00 / 1.00 | 0% of 7 |

- H1 is paired within each trial; trials with extraction or tier 1/2 errors are excluded.
- H2 uses only families with both variants (F1–F3) and a one-sided stratified permutation test. A and B are different tasks, so this is not a paired test, and B tasks are also larger, so the gap is not attributable to coupling alone.
- H4/H5 use every failing hidden seed, with all labels seen at its first failing event. H5's split (conservation law broken vs report mismatch only) is an automatic proxy for the pre-registered 'secondary omission vs primary logic' classification and must be checked against the transcripts.

## H3: invariant feedback loop (paired: same trial, first vs final turn)

| Model | Trials | Turn 0 pass | Final pass | Mean score gain | Fixed / broken | McNemar p | Mean revisions |
|---|---|---|---|---|---|---|---|
| gemma_26b | 15 | 60.0% | 100.0% | +0.347 | 6 / 0 | 0.031 | 0.47 |
| flash_lite | 15 | 60.0% | 93.3% | +0.243 | 5 / 0 | 0.062 | 0.67 |
