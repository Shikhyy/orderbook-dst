"""graders/trace_gen.py
Deterministic trace generator supporting five task profiles and trigger coverage reporting.
See docs/06_TASK_SPECS.md section 7 & 8, docs/07_GRADER_SPEC.md section 4.
"""
from dataclasses import dataclass, field

from exchange_core.types import BasketLeg, Event
from graders.detrng import DetRng

PROFILES = (
    "fee_heavy", "replace_heavy", "fix_noisy", "shock_heavy", "basket_heavy", "match_heavy",
    "funding_heavy", "crash_heavy",
)
TICK = 10_000
BASE_MARK = 100_000_000


@dataclass
class TraceResult:
    """The generated trace and metadata."""
    seed: int
    profile: str
    events: list[Event]
    accounts: dict[str, int]
    mark_price: int
    trigger_count: int = 0
    trigger_indices: list[int] = field(default_factory=list)
    invalid_count: int = 0


def _build_accounts() -> dict[str, int]:
    """Produce at least 3 trading accounts plus LIQ (Rule docs/07 section 4.4)."""
    return {
        "A1": 20_000_000_000,
        "A2": 20_000_000_000,
        "A3": 20_000_000_000,
        "LIQ": 100_000_000_000,
    }


def generate_trace(
    seed: int,
    profile: str,
    num_events: int = 200,
    clean_fix: bool = False,
) -> TraceResult:
    """Generate a deterministic event trace based on seed and profile.

    Profiles:
    - fee_heavy: Many sweeping orders generating fills and tier crossings.
    - replace_heavy: 40% REPLACE events, rate changes, partial fills.
    - fix_noisy: FIX messages with gaps, duplicates, poss_dup, and resets.
    - shock_heavy: Frequent PRICE_SHOCK events with positions.
    - basket_heavy: Atomic multi-leg baskets with IOC and POST_ONLY.
    - match_heavy: Order matching with IOC, POST_ONLY, self-trades and tight margin.
    - funding_heavy: Positions built by trading, FUNDING events with odd marks and large rates.
    - crash_heavy: Positions built by trading, PRICE_CRASH events with deep drops and spikes that
      bankrupt accounts (insurance draw, loss sharing, bad debt); account ids sort unlike numbers.
    """
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile: {profile}")

    rng = DetRng(seed)
    accounts = _build_accounts()
    if profile == "shock_heavy":
        accounts = {
            "A1": 1_000_000_000,
            "A2": 1_000_000_000,
            "A3": 1_000_000_000,
            "LIQ": 50_000_000_000,
        }
    if profile == "match_heavy":
        accounts = {
            "A1": 6_000_000_000,
            "A2": 6_000_000_000,
            "A3": 6_000_000_000,
            "LIQ": 100_000_000_000,
        }
    if profile == "funding_heavy":
        accounts = {
            "A1": 500_000_000,
            "A2": 500_000_000,
            "A3": 500_000_000,
            "LIQ": 100_000_000_000,
        }
    trading_accs = ["A1", "A2", "A3"]
    if profile == "crash_heavy":
        # Trading accounts "A10" to "A13" sort before "A2" as strings (rule R-W7).
        trading_accs = ["A1", "A2", "A3", "A10", "A11", "A12", "A13"]
        accounts = {
            "A1": 600_000_000,
            "A2": 600_000_000,
            "A3": 600_000_000,
            "A10": 600_000_000,
            "A11": 600_000_000,
            "A12": 600_000_000,
            "A13": 600_000_000,
            "LIQ": 100_000_000_000,
        }

    events: list[Event] = []
    trigger_indices: list[int] = []
    invalid_count = 0

    # Track order IDs placed for cancel and replace generation
    active_order_ids: list[int] = []
    order_prices: dict[int, int] = {}
    order_sides: dict[int, str] = {}
    next_sim_order_id = 1
    current_mark = BASE_MARK
    fix_seq = 1
    fix_epoch = 0

    for idx in range(num_events):
        is_invalid = rng.prob_pct(3)
        event: Event
        is_trigger = False

        if is_invalid:
            invalid_count += 1
            # Generate a defined invalid event (bad price, non-existent order, bad account)
            choice = rng.next_int(0, 2)
            if choice == 0:
                event = Event(
                    kind="NEW_LIMIT",
                    account=rng.choice(trading_accs),
                    side="BUY",
                    price=BASE_MARK + 5,  # not a multiple of TICK
                    qty=1,
                )
            elif choice == 1:
                event = Event(kind="CANCEL", order_id=999_999)  # unknown order
            else:
                event = Event(
                    kind="NEW_LIMIT",
                    account="UNKNOWN_ACC",
                    side="SELL",
                    price=BASE_MARK,
                    qty=1,
                )
            events.append(event)
            continue

        # Valid event generation based on profile
        if profile == "fee_heavy":
            # Profile 1: fee_heavy (F1 target).
            # Trigger event: An order that crosses the spread and triggers fee calculation.
            action = rng.next_int(0, 9)
            if action < 6:
                # 60% sweeping orders that cross the market
                side = rng.choice(["BUY", "SELL"])
                acc = rng.choice(trading_accs)
                # BUY sweeps at high price, SELL sweeps at low price
                price = BASE_MARK + 20 * TICK if side == "BUY" else BASE_MARK - 20 * TICK
                qty = rng.next_int(1, 5)
                event = Event(kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty)
                is_trigger = True
                active_order_ids.append(next_sim_order_id)
                next_sim_order_id += 1
            elif action < 9:
                # 30% passive resting limit orders
                side = rng.choice(["BUY", "SELL"])
                acc = rng.choice(trading_accs)
                shift = rng.next_int(1, 10) * TICK
                price = BASE_MARK - shift if side == "BUY" else BASE_MARK + shift
                qty = rng.next_int(1, 5)
                event = Event(kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty)
                active_order_ids.append(next_sim_order_id)
                next_sim_order_id += 1
            else:
                # 10% cancels
                oid = rng.choice(active_order_ids) if active_order_ids else 1
                event = Event(kind="CANCEL", order_id=oid)

        elif profile == "replace_heavy":
            # Profile 2: replace_heavy (F2 target).
            # Trigger event: A REPLACE event.
            action = rng.next_int(0, 9)
            if action < 4 and active_order_ids:
                # 40% REPLACE events (trigger)
                oid = rng.choice(active_order_ids)
                cur_price = order_prices.get(oid, BASE_MARK)
                replace_branch = rng.next_int(0, 2)
                if replace_branch == 0:
                    # Same price, quantity decrease (tests priority retention)
                    new_price = cur_price
                    new_qty = rng.next_int(1, 3)
                elif replace_branch == 1:
                    # Same price, quantity increase (tests priority loss)
                    new_price = cur_price
                    new_qty = rng.next_int(8, 16)
                else:
                    # Price change without crossing (tests priority loss on passive side)
                    side = order_sides.get(oid, "BUY")
                    if side == "BUY":
                        new_price = BASE_MARK - rng.next_int(0, 3) * TICK
                    else:
                        new_price = BASE_MARK + rng.next_int(1, 4) * TICK
                    new_qty = rng.next_int(1, 4)

                if rng.prob_pct(5):
                    new_qty = 100_000

                order_prices[oid] = new_price
                event = Event(kind="REPLACE", order_id=oid, new_price=new_price, new_qty=new_qty)
                is_trigger = True
            elif action == 4:
                # Rate change
                bps = rng.choice([1500, 2000, 2500, 3000])
                event = Event(kind="SET_MARGIN_RATE", bps=bps)
            elif action < 8:
                # New orders: 60% passive resting, 40% sweeping
                side = rng.choice(["BUY", "SELL"])
                acc = rng.choice(trading_accs)
                if rng.prob_pct(40):
                    price = BASE_MARK + 5 * TICK if side == "BUY" else BASE_MARK - 5 * TICK
                    qty = rng.next_int(2, 6)
                else:
                    shift = rng.next_int(0, 3) if side == "BUY" else rng.next_int(1, 4)
                    price = BASE_MARK - shift * TICK if side == "BUY" else BASE_MARK + shift * TICK
                    qty = rng.next_int(4, 10)
                event = Event(kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty)
                active_order_ids.append(next_sim_order_id)
                order_prices[next_sim_order_id] = price
                order_sides[next_sim_order_id] = side
                next_sim_order_id += 1
            else:
                oid = rng.choice(active_order_ids) if active_order_ids else 1
                event = Event(kind="CANCEL", order_id=oid)

        elif profile == "fix_noisy":
            # Profile 3: fix_noisy (F3 target).
            # Trigger event: A FIX_MSG or SESSION_RESET event.
            is_trigger = True
            if idx == 100:
                # Reset event at event 100
                event = Event(kind="SESSION_RESET", session="S1")
                fix_seq = 1
                fix_epoch += 1
            else:
                # FIX message wrapping order event
                side = rng.choice(["BUY", "SELL"])
                price = BASE_MARK + rng.next_int(-5, 5) * TICK
                if price <= 0:
                    price = BASE_MARK
                body = Event(
                    kind="NEW_LIMIT",
                    account=rng.choice(trading_accs),
                    side=side,
                    price=price,
                    qty=rng.next_int(1, 5),
                )
                active_order_ids.append(next_sim_order_id)
                next_sim_order_id += 1

                event = Event(
                    kind="FIX_MSG",
                    session="S1",
                    epoch=fix_epoch,
                    seq=fix_seq,
                    poss_dup=False,
                    body=body,
                )
                fix_seq += 1

        elif profile == "shock_heavy":
            # Profile 4: shock_heavy (F4 target).
            # Trigger event: A PRICE_SHOCK event.
            action = rng.next_int(0, 9)
            if action < 3:
                # 30% PRICE_SHOCK events (trigger)
                if rng.prob_pct(25):
                    current_mark = rng.choice([20_000_000, 500_000_000, 600_000_000])
                else:
                    shift = rng.choice([-70, -50, -30, 30, 50, 70]) * TICK * 100
                    current_mark = max(10_000_000, current_mark + shift)
                event = Event(kind="PRICE_SHOCK", mark_price=current_mark)
                is_trigger = True
            else:
                # 70% trading orders: mix of passive resting orders and crossing fills
                side = rng.choice(["BUY", "SELL"])
                acc = rng.choice(trading_accs)
                if rng.prob_pct(45):
                    # Passive resting limit order: locks margin so stage 1 cancels
                    # have locks to release
                    price = current_mark - 5 * TICK if side == "BUY" else current_mark + 5 * TICK
                    qty = rng.next_int(3, 8)
                else:
                    # Crossing order to build position
                    price = current_mark + (5 * TICK if side == "BUY" else -5 * TICK)
                    qty = rng.next_int(3, 8)
                event = Event(kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty)
                active_order_ids.append(next_sim_order_id)
                next_sim_order_id += 1

        elif profile == "basket_heavy":
            # Profile 5: basket_heavy (F5 target).
            # Trigger event: A BASKET event.
            action = rng.next_int(0, 9)
            if action < 4:
                # 40% BASKET events (trigger)
                acc = rng.choice(trading_accs)
                leg_count = rng.next_int(2, 3)
                legs: list[BasketLeg] = []
                for _ in range(leg_count):
                    leg_side = rng.choice(["BUY", "SELL"])
                    leg_flag = rng.choice(["IOC", "POST_ONLY"])
                    leg_price = BASE_MARK + rng.next_int(-5, 5) * TICK
                    if leg_price <= 0:
                        leg_price = BASE_MARK
                    legs.append(
                        BasketLeg(
                            side=leg_side, price=leg_price, qty=rng.next_int(1, 4), flag=leg_flag
                        )
                    )
                event = Event(kind="BASKET", account=acc, legs=tuple(legs))
                is_trigger = True
            else:
                # 60% standard limit orders to supply the book
                side = rng.choice(["BUY", "SELL"])
                acc = rng.choice(trading_accs)
                price = BASE_MARK + rng.next_int(-4, 4) * TICK
                if price <= 0:
                    price = BASE_MARK
                qty = rng.next_int(2, 8)
                event = Event(kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty)
                active_order_ids.append(next_sim_order_id)
                next_sim_order_id += 1

        elif profile == "match_heavy":
            # Profile 6: match_heavy (F6 target).
            # Trigger event: an order that crosses the book (fills, STP, IOC remainder,
            # or a POST_ONLY that would cross).
            action = rng.next_int(0, 9)
            side = rng.choice(["BUY", "SELL"])
            acc = rng.choice(trading_accs)
            near = BASE_MARK + rng.next_int(-3, 3) * TICK
            if action < 3:
                # 30% resting orders, some POST_ONLY
                flag = "POST_ONLY" if rng.prob_pct(30) else "NONE"
                shift = rng.next_int(0, 3) * TICK
                price = BASE_MARK - shift if side == "BUY" else BASE_MARK + shift
                qty = rng.next_int(1, 6)
                event = Event(
                    kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty, flag=flag
                )
                is_trigger = flag == "POST_ONLY"
                active_order_ids.append(next_sim_order_id)
                next_sim_order_id += 1
            elif action < 6:
                # 30% plain limit orders that often cross and rest the remainder
                qty = rng.next_int(1, 9)
                event = Event(kind="NEW_LIMIT", account=acc, side=side, price=near, qty=qty)
                is_trigger = True
                active_order_ids.append(next_sim_order_id)
                next_sim_order_id += 1
            elif action < 8:
                # 20% IOC orders (remainder is cancelled)
                price = BASE_MARK + (rng.next_int(0, 4) * TICK if side == "BUY"
                                     else -rng.next_int(0, 4) * TICK)
                qty = rng.next_int(2, 10)
                event = Event(
                    kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty, flag="IOC"
                )
                is_trigger = True
                active_order_ids.append(next_sim_order_id)
                next_sim_order_id += 1
            elif action < 9:
                # 10% large orders that sweep several levels and stress margin
                price = BASE_MARK + (6 * TICK if side == "BUY" else -6 * TICK)
                qty = rng.next_int(8, 20)
                event = Event(kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty)
                is_trigger = True
                active_order_ids.append(next_sim_order_id)
                next_sim_order_id += 1
            else:
                # 10% cancels
                oid = rng.choice(active_order_ids) if active_order_ids else 1
                event = Event(kind="CANCEL", order_id=oid)

        elif profile == "funding_heavy":
            # Profile 7: funding_heavy (F7 target).
            # Trigger event: a FUNDING event (payments, vault residual, waterfall).
            action = rng.next_int(0, 9)
            if action < 3:
                # 30% FUNDING events; rates beyond +/-3000 exercise the clamp
                rate = rng.next_int(-5000, 5000)
                if rng.prob_pct(10):
                    rate = 0
                event = Event(kind="FUNDING", bps=rate)
                is_trigger = True
            elif action < 4:
                # 10% price shocks to odd (non round) marks; some are large enough to
                # push thinly funded accounts into breach and create LIQ positions
                if rng.prob_pct(30):
                    current_mark = BASE_MARK + rng.next_int(-45_000_000, 45_000_000) + 7
                else:
                    current_mark = BASE_MARK + rng.next_int(-40_000, 40_000) * 37
                event = Event(kind="PRICE_SHOCK", mark_price=current_mark)
            elif action < 7:
                # 30% crossing orders to build and move positions
                side = rng.choice(["BUY", "SELL"])
                acc = rng.choice(trading_accs)
                price = BASE_MARK + (3 * TICK if side == "BUY" else -3 * TICK)
                qty = rng.next_int(1, 7)
                event = Event(kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty)
                active_order_ids.append(next_sim_order_id)
                next_sim_order_id += 1
            elif action < 9:
                # 20% passive orders that supply liquidity
                side = rng.choice(["BUY", "SELL"])
                acc = rng.choice(trading_accs)
                shift = rng.next_int(0, 2) * TICK
                price = BASE_MARK - shift if side == "BUY" else BASE_MARK + shift
                qty = rng.next_int(1, 7)
                event = Event(kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty)
                active_order_ids.append(next_sim_order_id)
                next_sim_order_id += 1
            else:
                oid = rng.choice(active_order_ids) if active_order_ids else 1
                event = Event(kind="CANCEL", order_id=oid)

        elif profile == "crash_heavy":
            # Profile 8: crash_heavy (F8 target).
            # Trigger event: a PRICE_CRASH event (waterfall plus bankruptcy procedure).
            action = rng.next_int(0, 99)
            if action < 20:
                # PRICE_CRASH events. Small steps leave small deficits (the insurance fund can
                # cover them), deep drops ruin longs, spikes ruin shorts, resets let the book
                # recover.
                kind_roll = rng.next_int(0, 9)
                if kind_roll < 4:
                    step = rng.next_int(-9, 9)
                    current_mark = max(10_000_000, current_mark + current_mark * step // 100)
                elif kind_roll < 6:
                    current_mark = rng.next_int(20_000_000, 70_000_000) + rng.next_int(0, 9) * 7
                elif kind_roll < 8:
                    current_mark = rng.next_int(150_000_000, 400_000_000) + rng.next_int(0, 9) * 7
                else:
                    current_mark = BASE_MARK
                event = Event(kind="PRICE_CRASH", mark_price=current_mark)
                is_trigger = True
            elif action < 88:
                # crossing orders to build positions on both sides
                side = rng.choice(["BUY", "SELL"])
                acc = rng.choice(trading_accs)
                price = BASE_MARK + (3 * TICK if side == "BUY" else -3 * TICK)
                qty = rng.next_int(1, 8)
                event = Event(kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty)
                active_order_ids.append(next_sim_order_id)
                next_sim_order_id += 1
            elif action < 95:
                # passive orders that supply liquidity
                side = rng.choice(["BUY", "SELL"])
                acc = rng.choice(trading_accs)
                shift = rng.next_int(0, 2) * TICK
                price = BASE_MARK - shift if side == "BUY" else BASE_MARK + shift
                qty = rng.next_int(1, 8)
                event = Event(kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty)
                active_order_ids.append(next_sim_order_id)
                next_sim_order_id += 1
            else:
                oid = rng.choice(active_order_ids) if active_order_ids else 1
                event = Event(kind="CANCEL", order_id=oid)

        if is_trigger:
            trigger_indices.append(idx)
        events.append(event)

    return TraceResult(
        seed=seed,
        profile=profile,
        events=events,
        accounts=accounts,
        mark_price=BASE_MARK,
        trigger_count=len(trigger_indices),
        trigger_indices=trigger_indices,
        invalid_count=invalid_count,
    )


def make_noisy_fix_trace(clean_trace: TraceResult, seed: int) -> list[Event]:
    """Create a noisy copy of a clean FIX trace with duplicates and reordering.

    Rule I4: Replay property.
    Must deliver all clean messages eventually, with duplicates and gaps introduced.
    """
    rng = DetRng(seed ^ 0xABCDEF12)
    noisy: list[Event] = []
    pending_buffer: list[Event] = []
    current_epoch = 0

    for ev in clean_trace.events:
        if ev.kind == "SESSION_RESET":
            # Flush pending buffer from prior epoch
            while pending_buffer:
                buf_ev = pending_buffer.pop(0)
                noisy.append(buf_ev)
            # Send an unfillable gap before reset to populate buffer (Rule R-S8)
            noisy.append(
                Event(
                    kind="FIX_MSG",
                    session=ev.session,
                    epoch=current_epoch,
                    seq=9999,
                    poss_dup=False,
                    body=Event(
                        kind="NEW_LIMIT",
                        account="A1",
                        side="BUY",
                        price=BASE_MARK,
                        qty=1,
                    ),
                )
            )
            noisy.append(ev)
            current_epoch += 1
            continue

        if ev.kind != "FIX_MSG":
            noisy.append(ev)
            continue

        # Occasionally delay a message into a pending buffer (creating a gap)
        if rng.prob_pct(25) and len(pending_buffer) < 2:
            pending_buffer.append(ev)
            continue

        # Occasionally send in-sequence message with poss_dup=True (Rule R-S4)
        if rng.prob_pct(15):
            ev_to_send = Event(
                kind=ev.kind,
                session=ev.session,
                epoch=ev.epoch,
                seq=ev.seq,
                poss_dup=True,
                body=ev.body,
            )
        else:
            ev_to_send = ev

        # Deliver current message
        noisy.append(ev_to_send)

        # If earlier messages are pending in network, ev_to_send was buffered by the engine.
        # Send a duplicate of the buffered message with body=None (Rule R-S5 / buffer overwrite)
        if pending_buffer and rng.prob_pct(35):
            noisy.append(
                Event(
                    kind=ev_to_send.kind,
                    session=ev_to_send.session,
                    epoch=ev_to_send.epoch,
                    seq=ev_to_send.seq,
                    poss_dup=True,
                    body=None,
                )
            )

        # Occasionally send a duplicate with poss_dup=True or False (seq < next_seq)
        if rng.prob_pct(20):
            dup = Event(
                kind=ev.kind,
                session=ev.session,
                epoch=ev.epoch,
                seq=ev.seq,
                poss_dup=rng.choice([True, False]),
                body=ev.body,
            )
            noisy.append(dup)

        # Flush any pending buffer messages
        while pending_buffer:
            buf_ev = pending_buffer.pop(0)
            noisy.append(buf_ev)

    # Deliver any remaining pending messages so no gap is left
    while pending_buffer:
        noisy.append(pending_buffer.pop(0))

    return noisy
