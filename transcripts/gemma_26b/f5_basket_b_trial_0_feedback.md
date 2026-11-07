# gemma_26b · f5_basket_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `gemma-4-26b-a4b-it` / `None` |
| Settings | `{"max_tokens": 8000, "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key_env": "GEMINI_API_KEY"}` |
| Mode | feedback_loop |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 17115 / 1524 |
| Latency (s) | 166.7273108959198 |
| Stop reason | – |
| Timestamp | 2026-11-05T18:02:03.693305+00:00 |
| Prompt | [`prompt.txt`](../../results/feedback/raw/gemma_26b/f5_basket_b/0/prompt.txt) (sha256 `7e553cc067af8c79…`) |
| Raw files | [`results/feedback/raw/gemma_26b/f5_basket_b/0/`](../../results/feedback/raw/gemma_26b/f5_basket_b/0) |

## Feedback-loop turns

| Turn | Score | Passed | First failure |
|---|---|---|---|
| 0 | 0.3875 | False | D1 event 2 report differs from reference |
| 1 | 1.0 | True | –  |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f5_basket_b/basket.py
+++ model/exchange_core/handlers/basket.py
@@ -1,56 +1,48 @@
 """exchange_core/handlers/basket.py
-Handle atomic BASKET event execution with rollback.
+Handler for atomic multi-leg basket orders.
 Rules R-A1 to R-A5. Target for task f5_basket_b.
 """
+from typing import Any
 from exchange_core.types import Event, Report
 
 
-def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
-    """Process an atomic multi-leg basket order.
-
-    Rules R-A1 to R-A5:
-    - R-A2: Take snapshot before leg 1. Process each leg in order as NEW_LIMIT.
-    - R-A3: An IOC leg succeeds if accepted and leaves is 0 after matching.
-            A POST_ONLY leg succeeds if accepted. A rejected leg fails.
-    - R-A4: If a leg fails, restore snapshot. Report BASKET_ROLLED_BACK(leg_index).
-            Discard reports of earlier legs.
-    - R-A5: If all legs succeed, report all leg reports in order + BASKET_COMMITTED.
-    """
-    # Rule R-A2: snapshot complete state before processing leg 1
+def handle_basket(engine: Any, event: Event) -> list[Report]:
+    """Process a BASKET event with all-or-nothing rollback semantics."""
+    # R-A2: Take a snapshot of the complete state before processing any leg.
     snap = engine.state.snapshot()
-
-    all_leg_reports: list[Report] = []
-
-    for leg_index, leg in enumerate(event.legs):
+    
+    all_reports: list[Report] = []
+    
+    for i, leg in enumerate(event.legs):
+        # R-A1/A2: Convert leg to NEW_LIMIT event.
         leg_event = Event(
             kind="NEW_LIMIT",
             account=event.account,
             side=leg.side,
             price=leg.price,
             qty=leg.qty,
-            flag=leg.flag,
+            flag=leg.flag
         )
+        
+        # Process the leg using engine.dispatch.
+        leg_reports = engine.dispatch(leg_event)
+        
+        # R-A3: Check if the leg succeeded.
+        # A leg is rejected if it returns a REJECTED report.
+        # For IOC legs, they must not have an IOC_REMAINDER cancellation.
+        failed = False
+        for r in leg_reports:
+            if r.kind == "REJECTED" or (r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"):
+                failed = True
+                break
+        
+        if failed:
+            # R-A4: If a leg fails, stop, restore, and report BASKET_ROLLED_BACK.
+            engine.state.restore(snap)
+            return [Report.basket_rolled_back(leg_index=i)]
+        
+        all_reports.extend(leg_reports)
 
-        leg_reports = engine.dispatch(leg_event)
-
-        # Rule R-A3: leg success evaluation
-        # 1. Any rejection fails the leg
-        if any(r.kind == "REJECTED" for r in leg_reports):
-            engine.state.restore(snap)
-            return [Report.basket_rolled_back(leg_index)]
-
-        # 2. IOC leg must have leaves == 0 after matching (cannot have IOC_REMAINDER)
-        if leg.flag == "IOC":
-            has_ioc_cancel = any(
-                r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"
-                for r in leg_reports
-            )
-            if has_ioc_cancel:
-                engine.state.restore(snap)
-                return [Report.basket_rolled_back(leg_index)]
-
-        all_leg_reports.extend(leg_reports)
-
-    # Rule R-A5: all legs succeeded
-    all_leg_reports.append(Report.basket_committed())
-    return all_leg_reports
+    # R-A5: If all legs succeed, report all leg reports in order, then BASKET_COMMITTED.
+    all_reports.append(Report.basket_committed())
+    return all_reports
```

## Author analysis

_Write after reading the reply: what the model got wrong and why, or whether the grader rejected a valid answer._

## Model reply (verbatim)

````text
<thought>*   Task: Implement `handle_basket(engine, event)`.
    *   Goal: Process a `BASKET` event atomically.
    *   Rule R-A1: `BASKET` event has `account` and `legs`. Each leg has `side`, `price`, `qty`, `flag` (`IOC` or `POST_ONLY`).
    *   Rule R-A2: Take state snapshot. Process legs in order as `NEW_LIMIT` events.
    *   Rule R-A3:
        *   `IOC` succeeds if accepted AND `leaves == 0` (no `IOC_REMAINDER` cancellation).
        *   `POST_ONLY` succeeds if accepted (must not cross).
        *   A rejected leg fails.
    *   Rule R-A4: If any leg fails, restore snapshot, report `BASKET_ROLLED_BACK(leg_index)`, discard earlier leg reports.
    *   Rule R-A5: If all succeed, report all leg reports in order, then `BASKET_COMMITTED`.

    *   The previous submission failed with "Invariant: D1: Report mismatch: event 2 report differs from reference".
    *   Looking at the previous code:
        ```python
        is_rejected = False
        for r in leg_reports:
            if r.kind == "REJECTED":
                is_rejected = True
                break
        ```
    *   The previous code did not handle the "IOC success" condition explicitly as defined in R-A3: "An IOC leg succeeds if it is accepted and `leaves` is 0... (it must not have an `IOC_REMAINDER` cancellation)".
    *   Wait, the `NEW_LIMIT` handler for `IOC` might return `ACCEPTED` even if `leaves > 0`? No, typically an `IOC` order that doesn't fill is cancelled immediately. If it's "accepted" but "leaves > 0", it means it was processed but didn't fill.
    *   Let's re-read R-A3 carefully: "An IOC leg succeeds if it is accepted and `leaves` is 0 after matching (it must not have an `IOC_REMAINDER` cancellation)."
    *   How do I check `leaves`? I don't have the `order_id` easily, but `engine.dispatch` returns reports.
    *   Wait, if a leg is `IOC`, the reports returned by `engine.dispatch` might include an `ACCEPTED` report and then some `FILL` reports.
    *   If `leaves` is not 0, does it produce a `CANCELLED` report with reason `IOC_REMAINDER`?
    *   The rule says: "it must not have an `IOC_REMAINDER` cancellation".
    *   This implies I should check the reports for a `CANCELLED` report with reason `IOC_REMAINDER`.
    *   Let's check the `Report` class in `types.py`: `cancelled(cls, order_id: int, reason: str) -> "Report"`.
    *   So if I see `Report(kind="CANCELLED", reason="IOC_REMAINDER")`, the leg failed.
    *   Also, if the leg is `REJECTED`, it failed.
    *   What about `POST_ONLY`? "A `POST_ONLY` leg succeeds if it is accepted (it must not cross)." This is likely handled inside `engine.dispatch` (returning `REJECTED` if it crosses).

    1.  Snapshot state.
    2.  Initialize `all_reports = []`.
    3.  Loop through `event.legs` with index `i`:
        a. Create `NEW_LIMIT` event for the leg.
        b. Call `engine.dispatch(leg_event)`.
        c. Check `leg_reports` for failure:
           - Any report with `kind == "REJECTED"`.
           - Any report with `kind == "CANCELLED"` and `reason == "IOC_REMAINDER"`.
        d. If failure found:
           - `engine.state.restore(snap)`.
           - return `[Report.basket_rolled_back(i)]`.
        e. Else:
           - `all_reports.extend(leg_reports)`.
    4.  After loop, append `Report.basket_committed()`.
    5.  Return `all_reports`.

    *   `test_leg_1_fails`: `leg0` has invalid price (not tick aligned). This should result in `REJECTED`.
    *   `test_post_only_fails_after_earlier_fills`: `leg0` (IOC) fills 2 units, `leg1` (POST_ONLY) would cross. `leg1` should be `REJECTED`.
    *   `test_reject_by_margin`: `leg1` fails margin check -> `REJECTED`.
    *   `test_reports_on_commit`: Returns `ACCEPTED`, `ACCEPTED`, `BASKET_COMMITTED`.

    *Wait*, looking at the `Report` definition:
    `@classmethod.cancelled(cls, order_id: int, reason: str) -> "Report"`
    So checking `r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"` is correct.

    *   The error "event 2 report differs from reference" in D1 invariant violation usually means the sequence or content of reports returned by `handle_basket` is slightly off.
    *   In `test_all_legs_succeed`: `reps[0] == Report.accepted(1)`, `reps[1] == Report.accepted(2)`, `reps[2] == Report.basket_committed()`.
    *   My logic: `all_reports.extend(leg_reports)`. If `leg_reports` is `[Report.accepted(1)]`, `[Report.accepted(2)]`, then `all_reports` becomes `[accepted(1), accepted(2)]`. Then `all_reports.append(Report.basket_committed())` makes it `[accepted(1), accepted(2), basket_committed()]`. This matches the test.

    *   What if `engine.dispatch` returns multiple reports per leg? (e.g., `ACCEPTED` followed by `FILL`).
    *   R-A5 says: "If all legs succeed, the engine reports the reports of all legs in order, then `BASKET_COMMITTED`."
    *   This means `all_reports.extend(leg_reports)` is correct.

    *   Is there any other failure mode?
    *   R-A3: "A rejected leg fails." -> `kind == "REJECTED"`.
    *   R-A3: "An IOC leg succeeds if it is accepted and `leaves` is 0 after matching (it must not have an `IOC_REMAINDER` cancellation)."
    *   If `engine.dispatch` handles the `IOC` order, and it doesn't fill completely, it might return `CANCELLED` with `reason="IOC_REMAINDER"`.

    *   `engine.dispatch` returns `list[Report]`.
    *   If a leg is `IOC` and it only partially fills, the `NEW_LIMIT` logic in the engine should ideally handle the partial fill and then cancel the remainder.
    *   If the rule says "it must not have an `IOC_REMAINDER` cancellation", it means if such a cancellation report exists, the basket leg is considered failed.

    *   The loop:
        ```python
        for i, leg in enumerate(event.legs):
            leg_event = Event(
                kind="NEW_LIMIT",
                account=event.account,
                side=leg.side,
                price=leg.price,
                qty=leg.qty,
                flag=leg.flag
            )
            leg_reports = engine.dispatch(leg_event)
            
            # Failure check
            failed = False
            for r in leg_reports:
                if r.kind == "REJECTED" or (r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"):
                    failed = True
                    break
            
            if failed:
                engine.state.restore(snap)
                return [Report.basket_rolled_back(i)]
            
            all_reports.extend(leg_reports)
        ```

    *   Is there anything else? R-A3: "A `POST_ONLY` leg succeeds if it is accepted (it must not cross)."
    *   If it crosses, the `NEW_LIMIT` handler should return `REJECTED`. So `r.kind == "REJECTED"` covers it.

    *   Wait, looking at `test_leg_1_fails`:
        `leg0 = BasketLeg(side="BUY", price=90_000_005, qty=2, flag="POST_ONLY")`
        `reps = eng.process(Event(kind="BASKET", account="A1", legs=(leg0,)))`
        `assert reps == [Report.basket_rolled_back(0)]`
        This confirms that if the first leg fails, we return `[Report.basket_rolled_back(0)]`.

    *   Check the `event.legs` type in `Event` class: `legs: tuple[BasketLeg, ...] = field(default_factory=tuple)`. Correct.

    *   One potential issue: In `test_all_legs_succeed`, the reports are `[Report.accepted(1), Report.accepted(2), Report.basket_committed()]`.
    *   If `engine.dispatch` for a `POST_ONLY` order that doesn't fill returns `[Report.accepted(id)]`, then `all_reports` will be correct.
    *   If an `IOC` order fills, it might return `[Report.accepted(id), Report.fill(...)]`. The rule says "reports of all individual legs in order". This implies all reports returned by `dispatch` for that leg.

    *   Is it possible for a leg to be "accepted" but `leaves` is not 0 for an `IOC` leg without a `CANCELLED` report?
    *   Rule R-A3 says: "...and `leaves` is 0 after matching (it must not have an `IOC_REMAINDER` cancellation)".
    *   This is a bit ambiguous. Does it mean the handler should check `leaves` or check for the cancellation report?
    *   Since I don't have direct access to the `Order` object easily (I'd have to find it in `engine.state.orders` by matching `order_id` from the `ACCEPTED` report), checking for `CANCELLED` with `IOC_REMAINDER` is much cleaner.
    *   Wait, the `ACCEPTED` report has `order_id`. I could find the order. But usually, in these tasks, the engine is designed so that the `REJECTED` or `CANCELLED` report is the indicator.

    *   Let's look at `Report` again.
    *   `accepted(cls, order_id: int) -> "Report"`
    *   `cancelled(cls, order_id: int, reason: str) -> "Report"`
    *   If a leg is `IOC` and doesn't fill, the engine typically:
        1.  Accepts the order.
        2.  Matches what it can.
        3.  Cancels the remainder.
    *   The reports would be `[ACCEPTED, FILL, FILL, ..., CANCELLED(reason="IOC_REMAINDER")]`.
    *   My loop would see `CANCELLED` and trigger a rollback. This matches R-A3.

    *   What about `POST_ONLY`?
    *   "A `POST_ONLY` leg succeeds if it is accepted (it must not cross)."
    *   If it crosses, the `NEW_LIMIT` handler should return `REJECTED`.
    *   If it doesn't cross, it returns `ACCEPTED` (and maybe `FILL` if it matches immediately? No, `POST_ONLY` shouldn't match immediately if it's on the book, but if there's a gap it might? Actually, `POST_ONLY` means it *must* be a maker. If it would match, it's a taker, so it's rejected.)
    *   So `POST_ONLY` success = `ACCEPTED` (and possibly `FILL` if it was a taker-but-maker order? No, `POST_ONLY` orders that would cross are rejected).
    *   Thus, `POST_ONLY` should only return `ACCEPTED` (and `FILL` if it somehow matched? Wait, if it's `POST_ONLY` and matches, it becomes a taker. But `POST_ONLY` is meant to prevent that).
    *   In most implementations, `POST_ONLY` either rests (returns `ACCEPTED`) or is rejected (returns `REJECTED`).

    *   Final Check on Rollback:
        "The engine reports only `BASKET_ROLLED_BACK(leg_index)` (0-based index of the failing leg). The reports of earlier legs are discarded."
        My code: `return [Report.basket_rolled_back(i)]`. Correct.

    *   `engine.dispatch` vs `engine.process`: The instructions say `engine.dispatch(event)` or `handle_new_limit(engine, event)`. `engine.dispatch` is safer.

    *   One more thing: The `test_reports_on_commit` test:
        `assert reps[0].kind == "ACCEPTED"`
        `assert reps[1].kind == "ACCEPTED"`
        `assert reps[2].kind == "BASKET_COMMITTED"`
        If `engine.dispatch` for `POST_ONLY` returns `[Report.accepted(id)]`, then `all_reports.extend` will add exactly that.

    *   Wait, I see a potential issue in my logic. What if the `IOC` leg is successful but the `engine.dispatch` returns `[ACCEPTED, FILL, FILL]`? My code will work. What if it returns `[ACCEPTED, FILL, FILL, CANCELLED(reason="IOC_REMAINDER")]`? My code will trigger a rollback. This is exactly what R-A3 says.

    *   Wait, is `IOC_REMAINDER` the correct reason?
    *   R-A3: "...it must not have an `IOC_REMAINDER` cancellation".
    *   This strongly suggests `IOC_REMAINDER` is a specific cancellation reason used by the engine.

    *   What about `POST_ONLY`?
    *   "A `POST_ONLY` leg succeeds if it is accepted (it must not cross)."
    *   If it crosses, it should be rejected. My code handles `REJECTED`.

    *   One edge case: `test_empty_basket`.
    *   `legs=()` loop won't run. `all_reports` is `[]`. `all_reports.append(Report.basket_committed())`. Returns `[Report.basket_committed()]`. Correct.

    *   Wait, I should ensure I'm importing everything correctly.
    *   `from exchange_core.types import Event, Report`
    *   `from typing import Any`
    *   `engine: Any`

    *   Let's double check the failure condition: `r.kind == "REJECTED" or (r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER")`.
    *   Is it possible for `r.reason` to be something else? The rule says "it must not have an `IOC_REMAINDER` cancellation". This implies if it *does* have it, it fails.

    *   Let's re-verify `test_leg_1_fails`.
    *   `leg0 = BasketLeg(side="BUY", price=90_000_005, qty=2, flag="POST_ONLY")`
    *   `eng.process(Event(kind="BASKET", account="A1", legs=(leg0,)))`
    *   `reps == [Report.basket_rolled_back(0)]`.
    *   Since `90_000_005` is not tick-aligned (tick is 10,000), `NEW_LIMIT` should return `REJECTED`. My code handles this.

    *   What if the error is `Report mismatch`?
    *   Looking at `test_all_legs_succeed`:
        `reps[0] == Report.accepted(1)`
        `reps[1] == Report.accepted(2)`
        `reps[2] == Report.basket_committed()`
    *   If `engine.dispatch` returns `[Report.accepted(1)]` and `[Report.accepted(2)]`, my code returns `[Report.accepted(1), Report.accepted(2), Report.basket_committed()]`.
    *   The `Report` objects must be exactly equal. `Report.accepted(1)` is `Report(kind="ACCEPTED", order_id=1)`.

    *   Is there anything else in R-A4?
    *   "The restore covers the book, all accounts, fee_vault, all volume values, both counters (next_order_id, next_prio_seq), and mark_price."
    *   `engine.state.restore(snap)` handles this as it's implemented in `EngineState.restore`.

    *   One detail: `engine.dispatch` vs `engine.process`.
    *   `engine.process(event)` is mentioned. In the `test_post_only_fails_after_earlier_fills`, it uses `eng.process(Event(...))`.
    *   Wait, `handle_basket` is called *inside* `engine.process`.
    *   The task says: "Use `engine.dispatch(event: Event) -> list[Report]` or `handle_new_limit(engine: "Engine", event: Event) -> list[Report]` for each leg event."
    *   I'll use `engine.dispatch`.

    *   Wait, I should check if `leg_reports` can be `None`.
    *   `engine.dispatch` returns `list[Report]`. So it should be a list.

    *   Final structure check:
    ```python
    def handle_basket(engine: Any, event: Event) -> list[Report]:
        snap = engine.state.snapshot()
        all_reports = []
        for i, leg in enumerate(event.legs):
            leg_event = Event(
                kind="NEW_LIMIT",
                account=event.account,
                side=leg.side,
                price=leg.price,
                qty=leg.qty,
                flag=leg.flag
            )
            leg_reports = engine.dispatch(leg_event)
            
            failed = False
            for r in leg_reports:
                if r.kind == "REJECTED" or (r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"):
                    failed = True
                    break
            
            if failed:
                engine.state.restore(snap)
                return [Report.basket_rolled_back(i)]
            
            all_reports.extend(leg_reports)
        
        all_reports.append(Report.basket_committed())
        return all_reports
    ```

    *   Wait, the rule R-A3 says "An IOC leg succeeds if it is accepted and leaves is 0 after matching".
    *   My code checks for a `CANCELLED` report with `IOC_REMAINDER`. This is a way to detect if `leaves > 0`.
    *   If the engine doesn't issue a `CANCELLED` report but just leaves the order in the book, that would be a violation of the `IOC` rule (an `IOC` order shouldn't leave anything in the book). But in this engine, `IOC` orders are immediate.
    *   Actually, if `leaves > 0`, it *must* be cancelled. And the rule specifically mentions `IOC_REMAINDER` cancellation. So my approach should be correct.

    *   One tiny thing: `engine.dispatch` is used for `NEW_LIMIT`.
    *   `engine.dispatch` for `NEW_LIMIT` will call `handle_new_limit`.
    *   Is there any chance `engine.dispatch` returns nothing? The return type is `list[Report]`, so `[]` is possible. If it's `[]`, `failed` remains `False`, and it continues. This is fine.

    *   Let's think if there's anything else. The `Invariant: D1: Report mismatch` error.
    *   Looking at `test_all_legs_succeed` again:
        `leg0 = BasketLeg(side="BUY", price=90_000_000, qty=2, flag="POST_ONLY")`
        `leg1 = BasketLeg(side="BUY", price=85_000_000, qty=2, flag="POST_ONLY")`
        `reps = eng.process(Event(kind="BASKET", account="A1", legs=(leg0, leg1)))`
        `assert len(reps) == 3`
        `assert reps[0] == Report.accepted(1)`
        `assert reps[1] == Report.accepted(2)`
        `assert reps[2] == Report.basket_committed()`
    *   Wait, if `leg0` is `POST_ONLY` and it's a maker, it should return `ACCEPTED`. My code would return `[Report.accepted(1), Report.accepted(2), Report.basket_committed()]`.
    *   The only way it would differ is if `leg_reports` contains more than one report. But if the test says `len(reps) == 3`, then `leg_reports` for each leg must have exactly 1 report.

    *   Could the mismatch be because I'm using `engine.dispatch` instead of `handle_new_limit`?
    *   The instructions say: "Call `engine.dispatch(event: Event) -> list[Report]` or `handle_new_limit(engine: "Engine", event: Event) -> list[Report]` for each leg event."
    *   So `engine.dispatch` is explicitly allowed.

    *   One more check: `event.account` vs `leg.account`.
    *   R-A1: "A BASKET event carries an `account` and a list of legs (`event.legs`)".
    *   My code uses `account=event.account`. Correct.

    *   Final code structure:
    ```python
    from typing import Any
    from exchange_core.types import Event, Report

    def handle_basket(engine: Any, event: Event) -> list[Report]:
        """Process a BASKET event with all-or-nothing rollback semantics."""
        snap = engine.state.snapshot()
        all_reports = []
        
        for i, leg in enumerate(event.legs):
            leg_event = Event(
                kind="NEW_LIMIT",
                account=event.account,
                side=leg.side,
                price=leg.price,
                qty=leg.qty,
                flag=leg.flag
            )
            
            leg_reports = engine.dispatch(leg_event)
            
            failed = False
            for r in leg_reports:
                if r.kind == "REJECTED" or (r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"):
                    failed = True
                    break
            
            if failed:
                engine.state.restore(snap)
                return [Report.basket_rolled_back(leg_index=i)]
            
            all_reports.extend(leg_reports)
            
        all_reports.append(Report.basket_committed())
        return all_reports
    ```
    This looks solid.

    *   Wait, I just noticed one thing. The previous submission used `engine.dispatch(leg_event)`.
    *   Is it possible `engine.dispatch` is not available on the `engine` object passed to `handle_basket`?
    *   The task description says: "`engine.dispatch(event: Event) -> list[Report]`: runs the event through the engine's own handler for `event.kind` and returns its reports."
    *   And it says: "Use `engine.dispatch(event: Event) -> list[Report]` or `handle_new_limit(engine: "Engine", event: Event) -> list[Report]` for each leg event."
    *   So `engine.dispatch` is definitely available.

    *   Let's check the `Report` equality.
    *   `Report` is a `dataclass(frozen=True)`. This means equality is based on all fields.
    *   `Report.accepted(1)` is `Report(kind="ACCEPTED", order_id=1, reason="", buy_order_id=0, sell_order_id=0, price=0, qty=0, taker_order_id=0, account="", mark_price=0, bps=0, session="", leg_index=0)`.
    *   This is standard.

    *   Is there any possibility that `engine.dispatch` returns reports that should *not* be in `all_reports`?
    *   "If all legs succeed, the engine reports the reports of all legs in order, then `BASKET_COMMITTED`."
    *   This means if `leg0` returns `[R1, R2]` and `leg1` returns `[R3]`, the total reports should be `[R1, R2, R3, BASKET_COMMITTED]`. My `extend` logic does exactly this.

    *   Wait, what if a leg's `engine.dispatch` returns a `REJECTED` report but also an `ACCEPTED` report? That's unlikely in a well-behaved engine, but my code would correctly identify the failure and roll back.

    *   Final check on R-A3 (IOC/POST_ONLY):
        - IOC: "An IOC leg succeeds if it is accepted and `leaves` is 0 after matching (it must not have an `IOC_REMAINDER` cancellation)."
        - My code: checks for `CANCELLED` with `reason="IOC_REMAINDER"`.
        - POST_ONLY: "A `POST_ONLY` leg succeeds if it is accepted (it must not cross)."
        - My code: checks for `REJECTED`. If it crosses, it's rejected. If it doesn't cross, it's accepted.

    *   Is it possible for an `IOC` order to be `REJECTED` instead of `CANCELLED`? Yes. My code handles `REJECTED` too.

    *   Could the error be the `import`?
    *   `from exchange_core.types import Event, Report`
    *   `from typing import Any`
    *   These are allowed.</thought>### FILE: exchange_core/handlers/basket.py
```python
"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from typing import Any
from exchange_core.types import Event, Report


def handle_basket(engine: Any, event: Event) -> list[Report]:
    """Process a BASKET event with all-or-nothing rollback semantics."""
    # R-A2: Take a snapshot of the complete state before processing any leg.
    snap = engine.state.snapshot()
    
    all_reports: list[Report] = []
    
    for i, leg in enumerate(event.legs):
        # R-A1/A2: Convert leg to NEW_LIMIT event.
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag
        )
        
        # Process the leg using engine.dispatch.
        leg_reports = engine.dispatch(leg_event)
        
        # R-A3: Check if the leg succeeded.
        # A leg is rejected if it returns a REJECTED report.
        # For IOC legs, they must not have an IOC_REMAINDER cancellation.
        failed = False
        for r in leg_reports:
            if r.kind == "REJECTED" or (r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"):
                failed = True
                break
        
        if failed:
            # R-A4: If a leg fails, stop, restore, and report BASKET_ROLLED_BACK.
            engine.state.restore(snap)
            return [Report.basket_rolled_back(leg_index=i)]
        
        all_reports.extend(leg_reports)

    # R-A5: If all legs succeed, report all leg reports in order, then BASKET_COMMITTED.
    all_reports.append(Report.basket_committed())
    return all_reports
```
````
