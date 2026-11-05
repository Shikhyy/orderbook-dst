## Bug Report

The engine in the "Buggy Target Files" section violates the specification. It was run on a short fixed event trace. All numbers are integers.

Initial state: A1 free_cash=600000000, A2 free_cash=600000000, A3 free_cash=600000000, A10 free_cash=600000000, A11 free_cash=600000000, A12 free_cash=600000000, A13 free_cash=600000000, LIQ free_cash=100000000000; mark_price=100000000; all positions 0; no resting orders; fee_vault=0.

Events (0-based index; the engine processes them in order):

0. NEW_LIMIT(account=A13, side=BUY, price=100030000, qty=5)
1. NEW_LIMIT(account=A3, side=SELL, price=99970000, qty=7)
2. NEW_LIMIT(account=A13, side=BUY, price=100030000, qty=1)
3. PRICE_CRASH(mark_price=279634628)
4. NEW_LIMIT(account=A11, side=BUY, price=100030000, qty=8)
5. NEW_LIMIT(account=A1, side=SELL, price=99970000, qty=4)
6. PRICE_CRASH(mark_price=299209051)

Symptom: at event 6 the engine returned the wrong reports.

Expected reports:
- MARK_SET(mark_price=299209051)
- LIQUIDATED(qty=-4, account=A1)
- INSURANCE_DRAWN(qty=1000300, account=A1)
- ADL_APPLIED(qty=78726493, account=A11)
- ADL_APPLIED(qty=118089741, account=A13)

Actual reports:
- MARK_SET(mark_price=299209051)
- LIQUIDATED(qty=-4, account=A1)
- INSURANCE_DRAWN(qty=1000300, account=A1)
- ADL_APPLIED(qty=78726494, account=A11)
- ADL_APPLIED(qty=118089740, account=A13)

Find the defect in the target file and return the corrected file. Change only what the specification requires; every other behaviour must stay exactly as it is.
