# nemotron_ultra · f1_fee_a · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `nvidia/nemotron-3-ultra-550b-a55b:free` / `nvidia/nemotron-3-ultra-550b-a55b:free` |
| Settings | `{"max_tokens": 16000, "base_url": "https://openrouter.ai/api/v1", "api_key_env": "OPENROUTER_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 6160 / 2022 |
| Latency (s) | 19.904462814331055 |
| Stop reason | stop |
| Timestamp | 2026-11-04T06:00:01.608790+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/nemotron_ultra/f1_fee_a/0/prompt.txt) (sha256 `3034abd905f45c04…`) |
| Raw files | [`results/main/raw/nemotron_ultra/f1_fee_a/0/`](../../results/main/raw/nemotron_ultra/f1_fee_a/0) |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f1_fee_a/fee_rule.py
+++ model/exchange_core/rules/fee_rule.py
@@ -1,42 +1,34 @@
-"""reference/f1_fee_a/fee_rule.py
-Reference solution for task f1_fee_a.
-Rules R-F2 and R-F3.
+"""exchange_core/rules/fee_rule.py
+Pure functions for taker fee and maker rebate calculation.
+Rules R-F2 and R-F3. Target for task f1_fee_a.
 """
 from exchange_core.config import EngineConfig
 from exchange_core.intmath import round_half_even
 
 
 def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
-    """Compute the taker fee for a fill using tier threshold logic.
+    """Compute the taker fee for a fill using tier threshold logic (Rule R-F2)."""
+    threshold = cfg.tier_threshold
+    ppm = cfg.ppm
+    t0 = cfg.taker_ppm_t0
+    t1 = cfg.taker_ppm_t1
 
-    Rule R-F2 [Declared]:
-    - If volume_before >= TIER_THRESHOLD:
-        fee = round_half_even(notional * TAKER_PPM_T1, PPM)
-    - If volume_before + notional <= TIER_THRESHOLD:
-        fee = round_half_even(notional * TAKER_PPM_T0, PPM)
-    - Otherwise the fill crosses the threshold. Split it:
-        below = TIER_THRESHOLD - volume_before
-        above = notional - below
-        fee = round_half_even(below * T0, PPM) + round_half_even(above * T1, PPM)
-    The engine rounds each part on its own. It does not round the sum.
-    """
-    if volume_before >= cfg.tier_threshold:
-        return round_half_even(notional * cfg.taker_ppm_t1, cfg.ppm)
+    if volume_before >= threshold:
+        # Entire fill at T1 rate
+        return round_half_even(notional * t1, ppm)
 
-    if volume_before + notional <= cfg.tier_threshold:
-        return round_half_even(notional * cfg.taker_ppm_t0, cfg.ppm)
+    if volume_before + notional <= threshold:
+        # Entire fill at T0 rate
+        return round_half_even(notional * t0, ppm)
 
-    below = cfg.tier_threshold - volume_before
+    # Fill crosses the threshold
+    below = threshold - volume_before
     above = notional - below
-    fee_below = round_half_even(below * cfg.taker_ppm_t0, cfg.ppm)
-    fee_above = round_half_even(above * cfg.taker_ppm_t1, cfg.ppm)
+    fee_below = round_half_even(below * t0, ppm)
+    fee_above = round_half_even(above * t1, ppm)
     return fee_below + fee_above
 
 
 def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
-    """Compute the maker rebate for a fill.
-
-    Rule R-F3 [Declared]:
-    The maker rebate for a fill is round_half_even(notional * MAKER_REBATE_PPM, PPM).
-    """
+    """Compute the maker rebate for a fill (Rule R-F3)."""
     return round_half_even(notional * cfg.maker_rebate_ppm, cfg.ppm)
```

## Author analysis

_Write after reading the reply: what the model got wrong and why, or whether the grader rejected a valid answer._

## Model reply (verbatim)

````text
### FILE: exchange_core/rules/fee_rule.py
```python
"""exchange_core/rules/fee_rule.py
Pure functions for taker fee and maker rebate calculation.
Rules R-F2 and R-F3. Target for task f1_fee_a.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import round_half_even


def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    """Compute the taker fee for a fill using tier threshold logic (Rule R-F2)."""
    threshold = cfg.tier_threshold
    ppm = cfg.ppm
    t0 = cfg.taker_ppm_t0
    t1 = cfg.taker_ppm_t1

    if volume_before >= threshold:
        # Entire fill at T1 rate
        return round_half_even(notional * t1, ppm)

    if volume_before + notional <= threshold:
        # Entire fill at T0 rate
        return round_half_even(notional * t0, ppm)

    # Fill crosses the threshold
    below = threshold - volume_before
    above = notional - below
    fee_below = round_half_even(below * t0, ppm)
    fee_above = round_half_even(above * t1, ppm)
    return fee_below + fee_above


def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
    """Compute the maker rebate for a fill (Rule R-F3)."""
    return round_half_even(notional * cfg.maker_rebate_ppm, cfg.ppm)
```
````
