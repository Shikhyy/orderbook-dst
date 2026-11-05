## Bug Report

The engine in the "Buggy Target Files" section violates the specification. It was run on a short fixed event trace. All numbers are integers.

Initial state: A1 free_cash=1000000000, A2 free_cash=1000000000, A3 free_cash=1000000000, LIQ free_cash=50000000000; mark_price=100000000; all positions 0; no resting orders; fee_vault=0.

Events (0-based index; the engine processes them in order):

0. NEW_LIMIT(account=A2, side=BUY, price=100050000, qty=7)
1. NEW_LIMIT(account=A3, side=SELL, price=100050000, qty=3)
2. PRICE_SHOCK(mark_price=170000000)
3. NEW_LIMIT(account=A1, side=BUY, price=100000005, qty=1)
4. NEW_LIMIT(account=A1, side=SELL, price=169950000, qty=6)
5. NEW_LIMIT(account=A3, side=SELL, price=169950000, qty=3)
6. NEW_LIMIT(account=A2, side=BUY, price=169950000, qty=4)
7. NEW_LIMIT(account=A3, side=SELL, price=170050000, qty=8)
8. NEW_LIMIT(account=A3, side=BUY, price=169950000, qty=8)
9. PRICE_SHOCK(mark_price=140000000)
10. PRICE_SHOCK(mark_price=500000000)

Symptom: at event 10 the engine returned the wrong reports.

Expected reports:
- MARK_SET(mark_price=500000000)
- LIQUIDATED(qty=-6, account=A1)
- CANCELLED(order_id=6, reason=RISK)
- CANCELLED(order_id=7, reason=RISK)

Actual reports:
- MARK_SET(mark_price=500000000)
- LIQUIDATED(qty=-6, account=A1)
- CANCELLED(order_id=6, reason=RISK)
- CANCELLED(order_id=7, reason=RISK)
- LIQUIDATED(qty=-1, account=A3)

Find the defect in the target file and return the corrected file. Change only what the specification requires; every other behaviour must stay exactly as it is.
