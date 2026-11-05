## Bug Report

The engine in the "Buggy Target Files" section violates the specification. It was run on a short fixed event trace. All numbers are integers.

Initial state: A1 free_cash=20000000000, A2 free_cash=20000000000, LIQ free_cash=100000000000; mark_price=100000000; all positions 0; no resting orders; fee_vault=0.

Events (0-based index; the engine processes them in order):

0. NEW_LIMIT(account=A2, side=SELL, price=100000000, qty=49)
1. NEW_LIMIT(account=A1, side=BUY, price=100000000, qty=49)

Symptom: after event 1 the state differs from the specified outcome: account A1 free_cash is 15090844990, expected 15086525000.

Find the defect in the target file and return the corrected file. Change only what the specification requires; every other behaviour must stay exactly as it is.
