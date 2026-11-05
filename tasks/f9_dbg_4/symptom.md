## Bug Report

The engine in the "Buggy Target Files" section violates the specification. It was run on a short fixed event trace. All numbers are integers.

Initial state: A1 free_cash=6000000000, A2 free_cash=6000000000, A3 free_cash=6000000000, LIQ free_cash=100000000000; mark_price=100000000; all positions 0; no resting orders; fee_vault=0.

Events (0-based index; the engine processes them in order):

0. NEW_LIMIT(account=A1, side=SELL, price=100010000, qty=6)
1. NEW_LIMIT(account=A2, side=SELL, price=99990000, qty=5)
2. NEW_LIMIT(account=A1, side=BUY, price=100000000, qty=4)

Symptom: after event 2 the invariant "Margin matches resting orders" is broken: order 2 lock 99990000 != expected 19998000.

Find the defect in the target file and return the corrected file. Change only what the specification requires; every other behaviour must stay exactly as it is.
