# 04 Venue Rulebook

This document is the single source of truth for engine behavior.
Each rule has an ID. Each task instruction cites rule IDs.

Note: This venue is a simulation. Some rules follow common exchange practice (for example FIX priority behavior and sequence handling). Other rules are declared conventions of this venue. Each rule is marked **[Common]** or **[Declared]**. Do not claim that a Declared rule is an industry standard.

## 1. Units and constants

| Name | Value | Meaning |
|---|---|---|
| Micro-USD | 1 USD = 1,000,000 | The unit of all amounts and prices |
| `TICK` | 10,000 | A price must be a multiple of `TICK` |
| `MARGIN_BPS_DEFAULT` | 2,000 | Initial margin rate (20%) in basis points |
| `MAINT_BPS` | 500 | Maintenance margin rate (5%) in basis points |
| `PPM` | 1,000,000 | Denominator for fee rates |
| `TAKER_PPM_T0` | 2,750 | Taker fee rate below the threshold |
| `TAKER_PPM_T1` | 1,850 | Taker fee rate at or above the threshold |
| `MAKER_REBATE_PPM` | 250 | Maker rebate rate |
| `TIER_THRESHOLD` | 5,000,010,000 | Volume that starts tier T1 (in micro-USD) |

`EngineConfig` holds these values. A test can use other values.

## 2. Arithmetic

**R-U1 [Declared].** All amounts, prices, and quantities are integers. The engine must not use `float`.

**R-U2 [Common].** `round_half_even(n, d)` divides `n` by `d` and rounds to the nearest integer. If the result is exactly halfway, it rounds to the even integer.
- Let `q, r = divmod(n, d)`.
- If `2*r > d`, return `q + 1`.
- If `2*r == d`, return `q + (q % 2)`.
- Otherwise return `q`.

Example: `round_half_even(25, 10) = 2`. `round_half_even(35, 10) = 4`. `round_half_even(26, 10) = 3`.

**R-U3 [Declared].** `ceil_div(n, d)` returns the smallest integer that is not below `n / d`. It equals `-((-n) // d)`.

## 3. Orders and the book

**R-B1 [Common].** An order has: `order_id`, `account`, `side` (BUY or SELL), `price`, `qty`, `cum_qty`, `prio_seq`, `margin_bps`, `lock`, `flag`.
`leaves` equals `qty - cum_qty`. A flag is `NONE`, `IOC`, or `POST_ONLY`.

**R-B2 [Common].** The book gives priority by price first and then by `prio_seq` (ascending). A BUY order with a higher price has priority. A SELL order with a lower price has priority.

**R-B3 [Declared].** `prio_seq` and `order_id` come from two counters in the state. Both counters start at 1. The engine does not use time.

**R-B4 [Declared].** The validation order for a NEW_LIMIT event is:
1. If the account does not exist, report `REJECTED(UNKNOWN_ACCOUNT)`.
2. If `qty <= 0`, or `price <= 0`, or `price % TICK != 0`, report `REJECTED(INVALID_ORDER)`.
3. If the flag is `POST_ONLY` and the order would match now, report `REJECTED(POST_ONLY_WOULD_CROSS)`.
4. Compute `lock = ceil_div(qty * price * margin_bps, 10000)` with the current `margin_bps` of the engine. If `free_cash < lock`, report `REJECTED(INSUFFICIENT_MARGIN)`.

A rejected order changes no state. A rejected order does not use a counter value.

**R-B5 [Declared].** When the order is valid, the engine does these steps in order:
1. Assign `order_id` and `prio_seq` from the counters. Add 1 to each counter.
2. Store the current `margin_bps` of the engine in the order.
3. Subtract `lock` from `free_cash`. Add `lock` to `locked_margin`. Store `lock` in the order.
4. Report `ACCEPTED(order_id)`.
5. Match the order (rules R-M1 to R-M4).
6. If the flag is `IOC` and `leaves > 0`, cancel the remainder (reason `IOC_REMAINDER`). Release the lock.
7. If the flag is not `IOC` and `leaves > 0`, add the order to the book as a resting order.

## 4. Matching

**R-M1 [Common].** A BUY order matches SELL resting orders with `price <= limit`. A SELL order matches BUY resting orders with `price >= limit`. The engine matches the best price first. At the same price, it matches the lowest `prio_seq` first.

**R-M2 [Common].** The fill price is the price of the resting order. The fill quantity is the smaller `leaves` of the two orders.

**R-M3 [Declared].** Self-trade prevention. If the resting order has the same account as the incoming order, the engine cancels the resting order with reason `STP`. It releases the lock of the resting order. It reports `CANCELLED(order_id, STP)`. It then continues to match. No fill occurs.

**R-M4 [Declared].** Effect of a fill with quantity `q`, price `p`, and notional `q * p`:
1. The buyer pays `notional` from `free_cash`. The buyer `position` increases by `q`.
2. The seller receives `notional` in `free_cash`. The seller `position` decreases by `q`.
3. For each of the two orders, add `q` to `cum_qty`.
4. For each of the two orders, compute `new_lock = ceil_div(leaves * order.price * order.margin_bps, 10000)`. Release `old_lock - new_lock` from `locked_margin` to `free_cash`. Store `new_lock` in the order.
5. Settle the fees (rules R-F1 to R-F3).
6. Report `FILL(buy_order_id, sell_order_id, price, qty, taker_order_id)`.

A fill can make `free_cash` negative. This is allowed.
A filled order (leaves 0) leaves the book.

**R-M5 [Declared].** Explicit lock release on full fill (OQ-04). When a fill results in `leaves == 0` for an order (including a fully filled taker order), `new_lock` is 0. In R-M4 step 4, the engine explicitly moves `old_lock` from `locked_margin` to `free_cash`.

## 5. Cancel and replace

**R-C1 [Common].** A CANCEL event for a resting order removes the order. It releases the full lock. It reports `CANCELLED(order_id, USER)`.
If the order is not resting, it reports `REJECTED(UNKNOWN_ORDER)`.

**R-P1 [Common, FIX semantics].** A REPLACE event carries `order_id`, `new_price`, and `new_qty`. The value `new_qty` is the new total order quantity (the FIX field OrderQty). It is not the new leaves.

**R-P2 [Declared].** The engine rejects a REPLACE event in this order:
1. If the order is not resting: `REJECTED(UNKNOWN_ORDER)`.
2. If `new_price <= 0` or `new_price % TICK != 0`: `REJECTED(INVALID_ORDER)`.
3. If `new_qty <= cum_qty`: `REJECTED(INVALID_REPLACE)`.
4. If the new price would match the opposite side of the book: `REJECTED(REPLACE_WOULD_CROSS)`.
5. If the new lock is more than the old lock and the difference is more than `free_cash`: `REJECTED(INSUFFICIENT_MARGIN)`.

A rejected REPLACE changes no state.

**R-P3 [Common, FIX semantics].** Priority after a valid REPLACE:
- If `new_price` equals the old price and `new_qty` is less than the old `qty`, the order keeps its `prio_seq` and its place in the queue.
- If `new_price` equals the old price and `new_qty` equals the old `qty`, nothing changes.
- In all other cases (price change, or quantity increase), the order gets a new `prio_seq` from the counter and goes to the back of the queue at its price.

**R-P4 [Declared].** After a valid REPLACE:
- The order keeps its `order_id`, `cum_qty`, and `margin_bps`.
- `qty` becomes `new_qty`. `price` becomes `new_price`.
- The new lock is `ceil_div(new_leaves * new_price * order.margin_bps, 10000)`. The rate is the rate stored in the order. It is not the current rate of the engine.
- The engine moves the difference between the old lock and the new lock between `free_cash` and `locked_margin`.
- The engine reports `REPLACED(order_id)`.

**R-P5 [Declared].** Replace crossing validation (OQ-05). In R-P2 check 4, the engine checks the raw best price on the opposite side of the book without filtering orders that belong to the same account. Self-trade prevention (R-M3) applies during order matching only, not during replace validation.

Example: A resting BUY order has `qty 10`, `cum_qty 4`, `price 100,000,000`, `margin_bps 2,000`, lock 120,000,000.
- REPLACE `new_qty 8`, same price: the order keeps priority. New leaves is 4. New lock is 80,000,000. The engine releases 40,000,000.
- REPLACE `new_qty 4`: reject with `INVALID_REPLACE`.
- REPLACE `new_price 101,000,000`, `new_qty 10`: the order gets a new `prio_seq`.

## 6. Margin rate

**R-G1 [Declared].** A SET_MARGIN_RATE event sets the `margin_bps` of the engine. It applies to orders accepted after the event only. A resting order keeps its stored rate. The engine reports `MARGIN_RATE_SET`.

Example: An order with `qty 10`, `price 100,000,000`, and rate 2,000 has lock 200,000,000. After the rate changes to 3,000, this lock stays at 200,000,000 for all later fills and replaces. A new order with the same size gets lock 300,000,000.

## 7. Fees

**R-F1 [Declared].** Each account has a `volume` (in micro-USD). It starts at 0. Each fill adds its notional to the `volume` of both accounts, after the fee for the fill is computed.

**R-F2 [Declared].** The taker fee for a fill uses `volume_before`, the volume of the taker before the fill:
- If `volume_before >= TIER_THRESHOLD`: `fee = round_half_even(notional * TAKER_PPM_T1, PPM)`.
- If `volume_before + notional <= TIER_THRESHOLD`: `fee = round_half_even(notional * TAKER_PPM_T0, PPM)`.
- Otherwise the fill crosses the threshold. Split it:
  - `below = TIER_THRESHOLD - volume_before`
  - `above = notional - below`
  - `fee = round_half_even(below * TAKER_PPM_T0, PPM) + round_half_even(above * TAKER_PPM_T1, PPM)`

The engine rounds each part on its own. It does not round the sum.

**R-F4 [Declared].** Fee threshold inclusive boundary (OQ-08). The tier threshold condition `volume_before + notional <= TIER_THRESHOLD` in R-F2 is inclusive. When `volume_before + notional == TIER_THRESHOLD`, the entire fill is evaluated under tier T0, and the split branch is not entered.

**R-F3 [Declared].** The maker rebate for a fill is `round_half_even(notional * MAKER_REBATE_PPM, PPM)`. The maker receives the rebate in `free_cash`. The taker pays the fee from `free_cash`. The `fee_vault` receives the fee and pays the rebate. The `fee_vault` can be negative.

Example: `volume_before = 4,999,980,000`, `notional = 300,000,000` (3 units at 100,000,000).
- `below = 30,000`. `above = 299,970,000`.
- `30,000 * 2,750 = 82,500,000`. Divided by 1,000,000 this is 82.5. Round half even gives 82.
- `299,970,000 * 1,850 = 554,944,500,000`. Divided by 1,000,000 this is 554,944.5. Round half even gives 554,944.
- The fee is 555,026. A round-half-up method gives 555,027 in total. A method that uses T1 for the whole fill gives 555,000.
- The rebate is 75,000.

## 8. Price shock and margin waterfall

**R-W1 [Declared].** A PRICE_SHOCK event sets the `mark_price`. The engine then runs the waterfall for each account except `LIQ`, in ascending account-id order.

**R-W2 [Declared].** For an account with `position != 0`:
- `avail = free_cash + position * mark_price`
- `req = ceil_div(abs(position) * mark_price * MAINT_BPS, 10000)`
- The account is in breach if `avail < req`.
An account with `position == 0` is never in breach.

**R-W3 [Declared].** Stage 1. If the account is in breach, the engine cancels all resting orders of the account in ascending `prio_seq` order. Each cancel releases the lock and reports `CANCELLED(order_id, RISK)`.

**R-W4 [Declared].** After stage 1, the engine computes the breach test again with the new `free_cash`. If the account is not in breach, the engine must not liquidate.

**R-W5 [Declared].** Stage 2. If the account is still in breach, the engine liquidates the whole position at `mark_price` against the account `LIQ`:
- If `position > 0`: the account sells `position` units to `LIQ`. The account receives `position * mark_price`. `LIQ` pays the same amount.
- If `position < 0`: the account buys `abs(position)` units from `LIQ`. The account pays `abs(position) * mark_price`. `LIQ` receives the same amount.
- The position of the account becomes 0. The position of `LIQ` changes by the opposite amount.
- No fee applies. The book does not change.
- The engine reports `LIQUIDATED(account, qty)` where `qty` is the signed position before liquidation.

Example: Account A is short 10 units. `free_cash = 1,050,000,000`. The mark moves to 101,000,000.
- `avail = 1,050,000,000 - 1,010,000,000 = 40,000,000`. `req = 50,500,000`. A is in breach.
- Case 1: A has locks of 20,000,000. Stage 1 releases them. `avail = 60,000,000`. This is not below `req`. No liquidation.
- Case 2: A has locks of 5,000,000. Stage 1 gives `avail = 45,000,000`. This is below `req`. Stage 2 liquidates.

**R-W6 [Declared].** The report order for PRICE_SHOCK is: `MARK_SET`, then for each account in ascending order the stage 1 cancels, then the `LIQUIDATED` report if it occurs.

**R-W7 [Declared].** Account iteration order (OQ-03). The ascending account-id order in R-W1 and R-W6 is lexicographic (standard string sorting order). For example, account `"10"` precedes account `"2"`.

## 9. FIX session sequence

**R-S1 [Common].** A FIX_MSG event carries `session`, `epoch`, `seq`, `poss_dup` (true or false), and `body`. The body is a NEW_LIMIT, CANCEL, or REPLACE event.

**R-S2 [Declared].** Each session has `epoch` (starts at 0), `next_seq` (starts at 1), and a `buffer` (a map from `seq` to message).

**R-S3 [Declared].** If `msg.epoch != session.epoch`, discard the message. Report `DISCARDED(EPOCH)`.

**R-S4 [Common].** If `msg.seq < next_seq`, discard the message. Report `DISCARDED(DUPLICATE)` if `poss_dup` is true. Report `DISCARDED(SEQ_TOO_LOW)` if `poss_dup` is false. State does not change.

**R-S5 [Common].** If `msg.seq == next_seq`, process the body. Add 1 to `next_seq`. Then, while the buffer holds `next_seq`, remove that message, process its body, and add 1 to `next_seq`.

**R-S6 [Common].** If `msg.seq > next_seq`, do not process the body. If the buffer holds `msg.seq`, discard the message and report `DISCARDED(DUPLICATE_BUFFERED)`. Otherwise store the message in the buffer and report `BUFFERED`.

**R-S7 [Common].** The flag `poss_dup` does not decide if the message is processed. Only the `seq` decides. A message with `poss_dup` true and `seq == next_seq` is the first arrival of that `seq`. The engine must process it.

**R-S8 [Declared].** A SESSION_RESET event for a session adds 1 to `epoch`, sets `next_seq` to 1, and empties the buffer. It reports `SESSION_RESET_DONE`.

**R-S9 [Declared].** The reports for a processed message are the reports of its body. The reports for drained buffer messages follow in ascending `seq` order.

## 10. Atomic basket

**R-A1 [Declared].** A BASKET event carries an `account` and a list of legs. A leg has `side`, `price`, `qty`, and `flag` (`IOC` or `POST_ONLY`).

**R-A2 [Declared].** The engine takes a snapshot of the complete state before leg 1. It then processes each leg in order as a NEW_LIMIT event for the account.

**R-A3 [Declared].** An `IOC` leg succeeds if it is accepted and `leaves` is 0 after matching. A `POST_ONLY` leg succeeds if it is accepted. A rejected leg fails.

**R-A4 [Declared].** If a leg fails, the engine stops. It restores the snapshot. The restore covers the book, all accounts, `fee_vault`, all `volume` values, both counters, and `mark_price`. The engine reports only `BASKET_ROLLED_BACK(leg_index)`. The reports of earlier legs are discarded.

**R-A5 [Declared].** If all legs succeed, the engine reports the reports of all legs in order, then `BASKET_COMMITTED`.

**R-A6 [Declared].** Basket rollback leg indexing (OQ-01). `BASKET_ROLLED_BACK(leg_index)` uses 0-based indexing (Python list convention). The first leg has index 0.

**R-A7 [Declared].** Basket IOC leg evaluation timing (OQ-02). For an `IOC` basket leg, the success check (`leaves == 0`) runs immediately after matching (R-M1 to R-M4) and before the R-B5 step 6 IOC remainder cancellation. If `leaves > 0` after matching, the leg fails and triggers rollback.

## 10b. Funding

**R-Y1 [Declared].** A FUNDING event carries a signed funding rate in parts per million in its `bps` field (`event.bps`; for this event the field is in ppm, not basis points). The engine clamps it to the range -3000 to +3000, both limits included (`MAX_FUNDING_PPM = 3000`). The clamped value is `rate`.

**R-Y2 [Declared].** If `rate != 0`, the engine processes every account with `position != 0` in ascending account-id order (the `LIQ` account included). For each such account: `notional = abs(position) * mark_price` and `amount = round_half_even(notional * abs(rate), PPM)`. The rounding is applied to this non-negative value. The account pays `amount` when it is long and `rate > 0`, or short and `rate < 0`. Otherwise it receives `amount`. A payment is subtracted from `free_cash`; a receipt is added to `free_cash`. `free_cash` can become negative. Locks, volume and positions do not change.

**R-Y3 [Declared].** Rounding is done per account, so the payments and receipts need not cancel. The engine adds the net of all payments (payments minus receipts, which can be negative) to `fee_vault`. Total cash plus `fee_vault` is unchanged.

**R-Y4 [Declared].** The first report is `FUNDING_APPLIED` with `bps = rate` (the clamped rate) and `qty` equal to the number of accounts processed in R-Y2. If `rate == 0`, no account is processed and `qty` is 0, even if accounts hold positions. If `rate != 0`, `qty` counts every account with `position != 0`, including one whose `amount` rounds to 0.

**R-Y5 [Declared].** After the payments, the engine always runs the margin waterfall at the current mark price, as if a PRICE_SHOCK event with `mark_price` equal to the current `mark_price` had arrived (rules R-W1 to R-W7). The reports of that waterfall follow `FUNDING_APPLIED`, in their own order (the first of them is `MARK_SET`). This also happens when `rate == 0`.

## 10c. Bankruptcy

**R-L0 [Declared].** A PRICE_CRASH event carries a `mark_price` and behaves exactly like PRICE_SHOCK (rules R-W1 to R-W7), with one addition. Right after each `LIQUIDATED` report for an account X, the engine runs the bankruptcy procedure of this section for X and appends its reports directly after that `LIQUIDATED` report, before it examines the next account. The procedure receives X and `pre_position`, the signed position of X before the liquidation (the `qty` of the `LIQUIDATED` report). The accounts are examined in the order of R-W1 and the live state is read: cash that the procedure takes from an account that comes later in the order counts when that account is examined. An account that was already examined is not examined again. PRICE_SHOCK never runs the procedure.

**R-L1 [Declared].** After the liquidation, X has `position == 0` and no resting order. The deficit of X is `max(0, -free_cash)` of X at that moment. If the deficit is 0, nothing changes and the procedure returns no report.

**R-L2 [Declared].** The fee vault pays first. `cover = min(deficit, max(0, fee_vault))`. If `cover > 0`, `fee_vault` decreases by `cover`, `free_cash` of X increases by `cover`, and the procedure reports `INSURANCE_DRAWN(account=X, qty=cover)`. The rest is `remaining = deficit - cover`. If `remaining == 0`, the procedure ends.

**R-L3 [Declared].** The rest is shared by the accounts on the other side of the liquidated position. An account is eligible when it is neither `LIQ` nor X and its position is not 0 and has the opposite sign to `pre_position`. The weight of an eligible account is `abs(position)`. With `total` the sum of all weights, each eligible account first gets `base = remaining * weight // total` (floor). The units that remain, `leftover = remaining - sum(base)`, are always fewer than the number of eligible accounts. Sort the eligible accounts by descending weight; accounts with the same weight are sorted by ascending account id (string order, as in R-W7). Each of the first `leftover` accounts in this order gets one more unit. The result is the `share` of each account. Each eligible account pays its `share` from `free_cash` (the cash can become negative; no waterfall, no cancel and no other check runs for it at this time). `free_cash` of X increases by `remaining`. For each account with `share > 0`, in ascending account-id order (string order), the procedure reports `ADL_APPLIED(account, qty=share)`.

**R-L4 [Declared].** If `remaining > 0` and no account is eligible, nothing else changes: X keeps its negative cash and the procedure reports `BAD_DEBT(account=X, qty=remaining)`.

**R-L5 [Declared].** Order of the reports of the procedure: `INSURANCE_DRAWN` (if any), then all `ADL_APPLIED` reports, or `BAD_DEBT`; never both. Total cash plus `fee_vault` is unchanged by the procedure.

## 11. Report reference

| Report | Fields |
|---|---|
| `ACCEPTED` | `order_id` |
| `REJECTED` | `reason` |
| `FILL` | `buy_order_id`, `sell_order_id`, `price`, `qty`, `taker_order_id` |
| `CANCELLED` | `order_id`, `reason` (USER, IOC_REMAINDER, STP, RISK) |
| `REPLACED` | `order_id` |
| `BUFFERED` | none |
| `DISCARDED` | `reason` (EPOCH, DUPLICATE, SEQ_TOO_LOW, DUPLICATE_BUFFERED) |
| `LIQUIDATED` | `account`, `qty` |
| `MARK_SET` | `mark_price` |
| `MARGIN_RATE_SET` | `bps` |
| `SESSION_RESET_DONE` | `session` |
| `BASKET_COMMITTED` | none |
| `BASKET_ROLLED_BACK` | `leg_index` |
| `FUNDING_APPLIED` | `bps` (clamped rate), `qty` (accounts processed) |
| `INSURANCE_DRAWN` | `account`, `qty` (amount paid from the fee vault) |
| `ADL_APPLIED` | `account`, `qty` (loss share paid by that account) |
| `BAD_DEBT` | `account`, `qty` (loss that nobody could take) |

## 12. Development and operational conventions

**R-X1 [Declared].** Environment and skill intent (OQ-06). When external development skills are not installed in the execution environment, their requirements are fulfilled by applying their underlying intent directly: write plans in ASD-STE100 prose, write tests first, and verify gate commands by hand.

**R-X2 [Declared].** Missing policy files scaffolding (OQ-07). Development policy files referenced in user instructions but omitted from initial bundles are created during M0 scaffolding with contents matching repository specifications, confirmed before merge.
