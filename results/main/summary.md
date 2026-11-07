# OrderBook-DST Evaluation Summary

- Run date (UTC): 2026-11-06T07:09:39.741130+00:00
- Git SHA: `c07d5a4ca1124aa3bdcaa68380382226f39ef4db`
- Total trials: 329

## Headline results

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

## Per-task results (passes / trials, mean score)

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

## Outcome of each trial by task

First failure per trial: invariant ID (I1–I4), D1 = report/state differs from reference, T1/T2 = failed visible tests or checkpoints, or an extraction/import error.

**nemotron_ultra**

- `f1_fee_a`: pass×3
- `f1_fee_b`: pass×3
- `f2_replace_a`: pass×3
- `f2_replace_b`: pass×3
- `f3_fix_a`: pass×3
- `f3_fix_b`: pass×3
- `f4_waterfall_b`: pass×3
- `f5_basket_b`: pass×3
- `f6_match_b`: pass×3
- `f7_funding_b`: pass×3
- `f8_adl_b`: pass×3

**mistral_large**

- `f1_fee_a`: pass×3
- `f1_fee_b`: pass×3
- `f2_replace_a`: D1×1, pass×2
- `f2_replace_b`: pass×3
- `f3_fix_a`: pass×3
- `f3_fix_b`: pass×3
- `f4_waterfall_b`: pass×3
- `f5_basket_b`: pass×3
- `f6_match_b`: OUTPUT_TRUNCATED×1, pass×2
- `f7_funding_b`: pass×3
- `f8_adl_b`: pass×3

**gemma_26b**

- `f1_fee_a`: pass×3
- `f1_fee_b`: T2_ERROR×3
- `f2_replace_a`: pass×3
- `f2_replace_b`: pass×3
- `f3_fix_a`: pass×3
- `f3_fix_b`: pass×3
- `f4_waterfall_b`: pass×3
- `f5_basket_b`: D1×1, pass×2
- `f6_match_b`: D1×1, I3×1, pass×1
- `f7_funding_b`: pass×3
- `f8_adl_b`: pass×3

**flash_lite**

- `f1_fee_a`: pass×3
- `f1_fee_b`: pass×3
- `f2_replace_a`: pass×3
- `f2_replace_b`: D1×1, T2_ERROR×1, pass×1
- `f3_fix_a`: pass×3
- `f3_fix_b`: pass×3
- `f4_waterfall_b`: D1×2, pass×1
- `f5_basket_b`: D1×2, pass×1
- `f6_match_b`: pass×3
- `f7_funding_b`: pass×3
- `f8_adl_b`: I1×1, pass×2

**nemotron_nano**

- `f1_fee_a`: pass×3
- `f1_fee_b`: OUTPUT_TRUNCATED×1, T2_ERROR×2
- `f2_replace_a`: pass×3
- `f2_replace_b`: T2_ERROR×3
- `f3_fix_a`: OUTPUT_TRUNCATED×1, pass×2
- `f3_fix_b`: T2_ERROR×1, pass×2
- `f4_waterfall_b`: OUTPUT_TRUNCATED×2, pass×1
- `f5_basket_b`: D1×2, OUTPUT_TRUNCATED×1
- `f6_match_b`: OUTPUT_TRUNCATED×3
- `f7_funding_b`: I1×1, OUTPUT_TRUNCATED×2
- `f8_adl_b`: OUTPUT_TRUNCATED×1, T2_FAIL×1, pass×1 — near miss trials: [1]

**ministral_8b**

- `f1_fee_a`: pass×3
- `f1_fee_b`: T2_ERROR×1, pass×2
- `f2_replace_a`: pass×3
- `f2_replace_b`: D1×1, I2×1, T2_ERROR×1
- `f3_fix_a`: pass×3
- `f3_fix_b`: I4×2, pass×1
- `f4_waterfall_b`: I2×1, T2_ERROR×2
- `f5_basket_b`: D1×3
- `f6_match_b`: I2×1, T2_ERROR×2
- `f7_funding_b`: D1×2, I1×1
- `f8_adl_b`: D1×3

**gemini_35_flash**

- `f1_fee_a`: pass×3
- `f1_fee_b`: pass×3
- `f2_replace_a`: pass×3
- `f2_replace_b`: pass×3
- `f3_fix_a`: pass×3
- `f4_waterfall_b`: pass×3
- `f5_basket_b`: D1×3
- `f6_match_b`: pass×2

## Sanity checks

- ⚠️ Little headroom: nemotron_ultra passes 100% of trials. The eval may no longer show a limitation for this model.
- ⚠️ `f1_fee_a` is passed by every trial of every model: it does not separate models.
- ⚠️ mistral_large: 1 trials ran out of output tokens before giving an answer (reasoning models can spend the whole budget thinking). Raise max_tokens in models.toml if the provider allows it, then re-run those trials; report the remaining ones as a token-budget limit.
- ⚠️ nemotron_nano: 11 trials ran out of output tokens before giving an answer (reasoning models can spend the whole budget thinking). Raise max_tokens in models.toml if the provider allows it, then re-run those trials; report the remaining ones as a token-budget limit.
- ⚠️ gemini_35_flash: 23 of 24 trials recorded; the run is incomplete (resume it).

## Pre-registered hypotheses (computed; see HYPOTHESES.md)

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

## F9: diagnose and fix (exploratory; not part of H1–H5)

The model gets the specification, a handler with one defect and the first failing step of a short trace, and returns the corrected file. Each task is graded exactly like the task it is graded as. These trials are not in the headline table or in H1–H5. `impl` is the same model's passes on the implementation task (written from scratch) that the F9 task is graded as.

| Task (graded as) | nemotron_ultra | mistral_large | gemma_26b | flash_lite | ministral_8b | nemotron_nano |
|---|---|---|---|---|---|---|
| `f9_dbg_1` (`f1_fee_b`) | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 0/3 | 3/3 (1.00), impl 3/3 | 0/3 (0.08), impl 2/3 | 3/3 (1.00), impl 0/3 |
| `f9_dbg_2` (`f4_waterfall_b`) | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 1/3 | 3/3 (1.00), impl 0/3 | 0/3 (0.00), impl 1/3 |
| `f9_dbg_3` (`f5_basket_b`) | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 0/3 (0.38), impl 2/3 | 3/3 (1.00), impl 1/3 | 0/3 (0.38), impl 0/3 | 1/3 (0.33), impl 0/3 |
| `f9_dbg_4` (`f6_match_b`) | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 2/3 | 3/3 (1.00), impl 1/3 | 3/3 (1.00), impl 3/3 | 2/3 (0.74), impl 0/3 | 1/3 (0.33), impl 0/3 |
| `f9_dbg_5` (`f7_funding_b`) | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 2/3 (0.68), impl 0/3 | 2/3 (0.67), impl 0/3 |
| `f9_dbg_6` (`f8_adl_b`) | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 3/3 | 3/3 (1.00), impl 2/3 | 3/3 (1.00), impl 0/3 | 3/3 (1.00), impl 1/3 |
