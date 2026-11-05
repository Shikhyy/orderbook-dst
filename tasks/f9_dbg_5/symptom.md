## Bug Report

The engine in the "Buggy Target Files" section violates the specification. It was run on a short fixed event trace. All numbers are integers.

Initial state: A1 free_cash=500000000, A2 free_cash=500000000, A3 free_cash=500000000, LIQ free_cash=100000000000; mark_price=100000000; all positions 0; no resting orders; fee_vault=0.

Events (0-based index; the engine processes them in order):

0. FUNDING(bps=-4256)
1. FUNDING(bps=-2817)
2. PRICE_SHOCK(mark_price=101412956)
3. NEW_LIMIT(account=A3, side=SELL, price=99970000, qty=4)
4. NEW_LIMIT(account=A3, side=BUY, price=100030000, qty=6)
5. NEW_LIMIT(account=A2, side=SELL, price=99970000, qty=6)
6. NEW_LIMIT(account=A1, side=BUY, price=100030000, qty=4)
7. NEW_LIMIT(account=A2, side=BUY, price=99990000, qty=3)
8. NEW_LIMIT(account=A2, side=BUY, price=100030000, qty=2)
9. NEW_LIMIT(account=A2, side=SELL, price=100020000, qty=2)
10. FUNDING(bps=-1103)
11. FUNDING(bps=-4881)
12. PRICE_SHOCK(mark_price=98642211)
13. FUNDING(bps=-1373)

Symptom: after event 13 the invariant "No money created or destroyed" is broken: total money 101500000001 != initial 101500000000.

Find the defect in the target file and return the corrected file. Change only what the specification requires; every other behaviour must stay exactly as it is.
