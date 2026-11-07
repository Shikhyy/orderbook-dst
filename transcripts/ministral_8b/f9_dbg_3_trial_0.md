# ministral_8b · f9_dbg_3 · trial 0 — failure (lowest score)

| Field | Value |
|---|---|
| Model ID (requested / served) | `ministral-8b-latest` / `ministral-8b-latest` |
| Settings | `{"max_tokens": 8000, "base_url": "https://api.mistral.ai/v1", "api_key_env": "MISTRAL_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 0.3806 (0.7777777777777778 / 0.75 / 0.0) |
| Outcome | I1 |
| Error | – |
| Tokens in / out | 7921 / 349 |
| Latency (s) | 11.274992942810059 |
| Stop reason | stop |
| Timestamp | 2026-11-05T19:21:55.860886+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/ministral_8b/f9_dbg_3/0/prompt.txt) (sha256 `354a565e3e52f5db…`) |
| Raw files | [`results/main/raw/ministral_8b/f9_dbg_3/0/`](../../results/main/raw/ministral_8b/f9_dbg_3/0) |

## First failure (hidden trace)

- Seed 8000, event 0: **I1** — Rollback restores complete state
- Message: `state hash after rolled-back basket at event 0 differs`

```json
{
  "before": "b1e3a79649cf52869191961b745f9826e2add17f46eab069b4c786c718b7c7d8",
  "after": "2a675bad5e0e2d3fe2d2ca7bd239270858295677184a8491c0bafb9ecf1fe41e"
}
```

## Labels on all failing hidden seeds

I1_ROLLBACK×20 (over 20 failing seeds of 20)

## Author analysis

_Write after reading the reply: what the model got wrong and why, or whether the grader rejected a valid answer._

## Model reply (verbatim)

````text
### FILE: exchange_core/handlers/basket.py
```python
"""exchange_core/handlers/basket.py"""
from exchange_core.types import Event, Report

def _rollback(engine, snap):
    next_id = engine.state.next_order_id
    engine.state.restore(snap)
    engine.state.next_order_id = next_id

def handle_basket(engine: "Engine", event: Event) -> list[Report]:
    snap = engine.state.snapshot()
    all_leg_reports: list[Report] = []
    next_order_id = engine.state.next_order_id

    for leg_index, leg in enumerate(event.legs):
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag,
        )

        leg_reports = engine.dispatch(leg_event)

        if any(r.kind == "REJECTED" for r in leg_reports):
            _rollback(engine, snap)
            return [Report.basket_rolled_back(leg_index)]

        if leg.flag == "IOC":
            has_ioc_cancel = any(
                r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"
                for r in leg_reports
            )
            if has_ioc_cancel:
                _rollback(engine, snap)
                return [Report.basket_rolled_back(leg_index)]

        all_leg_reports.extend(leg_reports)

    all_leg_reports.append(Report.basket_committed())
    return all_leg_reports
```
````
