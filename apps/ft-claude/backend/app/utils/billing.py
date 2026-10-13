"""Billing-cycle arithmetic shared by the subscriptions and savings routers."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from dateutil.relativedelta import relativedelta

from app.models import BillingCycle

# How many charges of each cycle land in a year. Weekly uses 52 rather than
# 52.18 so a ₹100/week sub reads as ₹433.33/month, matching what people
# usually expect from "×52÷12".
_PER_YEAR = {
    BillingCycle.weekly: Decimal(52),
    BillingCycle.monthly: Decimal(12),
    BillingCycle.quarterly: Decimal(4),
    BillingCycle.yearly: Decimal(1),
}

_STEP = {
    BillingCycle.weekly: relativedelta(weeks=1),
    BillingCycle.monthly: relativedelta(months=1),
    BillingCycle.quarterly: relativedelta(months=3),
    BillingCycle.yearly: relativedelta(years=1),
}

CENT = Decimal("0.01")


def yearly_cost(amount: Decimal, cycle: BillingCycle) -> Decimal:
    return (Decimal(amount) * _PER_YEAR[cycle]).quantize(CENT, ROUND_HALF_UP)


def monthly_cost(amount: Decimal, cycle: BillingCycle) -> Decimal:
    return (Decimal(amount) * _PER_YEAR[cycle] / 12).quantize(CENT, ROUND_HALF_UP)


def next_due(d: date, cycle: BillingCycle) -> date:
    """The following due date. relativedelta clamps month-ends, so a sub due
    Jan 31 moves to Feb 28/29."""
    return d + _STEP[cycle]


def guess_cycle(gap_days: float) -> BillingCycle:
    """Map an average gap between repeated charges to the nearest cycle."""
    if gap_days < 15:
        return BillingCycle.weekly
    if gap_days < 60:
        return BillingCycle.monthly
    if gap_days < 200:
        return BillingCycle.quarterly
    return BillingCycle.yearly
