## Bug Report

The engine in the "Buggy Target Files" section violates the specification. It was run on a short fixed event trace. All numbers are integers.

Initial state: A1 free_cash=20000000000, A2 free_cash=20000000000, A3 free_cash=20000000000, LIQ free_cash=100000000000; mark_price=100000000; all positions 0; no resting orders; fee_vault=0.

Events (0-based index; the engine processes them in order):

0. BASKET(account=A3, legs=[{'side': 'SELL', 'price': 99970000, 'qty': 2, 'flag': 'POST_ONLY'}, {'side': 'BUY', 'price': 100010000, 'qty': 2, 'flag': 'IOC'}, {'side': 'BUY', 'price': 100040000, 'qty': 3, 'flag': 'IOC'}])
1. NEW_LIMIT(account=A1, side=SELL, price=99980000, qty=6)

Symptom: at event 1 the engine returned the wrong reports.

Expected reports:
- ACCEPTED(order_id=1)

Actual reports:
- ACCEPTED(order_id=3)

Find the defect in the target file and return the corrected file. Change only what the specification requires; every other behaviour must stay exactly as it is.
