from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import (
    Category, SpendingCap, Subscription, SubscriptionStatus, SubscriptionUsage,
    Transaction, TxnType, User,
)
from app.schemas import (
    SavingsPlan, CategorySavingsItem, SubscriptionSavingsItem, SpendingCapIn,
)
from app.utils.billing import CENT

router = APIRouter(prefix="/savings", tags=["savings"])

WASTEFUL_USAGE = (SubscriptionUsage.rarely, SubscriptionUsage.unused)
ZERO = Decimal("0")


def _q(d: Decimal) -> Decimal:
    return Decimal(d).quantize(CENT, ROUND_HALF_UP)


def _rate(income: Decimal, expense: Decimal) -> Optional[Decimal]:
    if income <= 0:
        return None
    return _q((income - expense) / income * 100)


def _expense_by_category(db: Session, start: date, end: date) -> dict[int, Decimal]:
    rows = (
        db.query(Transaction.category_id, func.coalesce(func.sum(Transaction.amount), 0))
        .filter(Transaction.type == TxnType.expense, Transaction.txn_date >= start, Transaction.txn_date <= end)
        .group_by(Transaction.category_id)
        .all()
    )
    return {cid: Decimal(total) for cid, total in rows}


@router.get("/plan", response_model=SavingsPlan)
def savings_plan(
    months: int = Query(3, ge=1, le=12),
    cut_pct: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Where the household could save, from the last `months` *full* months
    of spending (the current partial month would drag averages down):

    1. Cancel active subscriptions rated "rarely" or "unused".
    2. Trim each non-essential category by `cut_pct`, or down to its
       adopted cap if one is set. A flagged subscription's cost is taken
       out of its category's baseline first so the same rupee isn't counted
       as saved twice.

    Essential categories are listed for context but never targeted."""
    today = date.today()
    month_start = today.replace(day=1)
    window_start = month_start - relativedelta(months=months)
    window_end = month_start - relativedelta(days=1)

    totals = dict(
        db.query(Transaction.type, func.coalesce(func.sum(Transaction.amount), 0))
        .filter(Transaction.txn_date >= window_start, Transaction.txn_date <= window_end)
        .group_by(Transaction.type)
        .all()
    )
    # Divide by months that actually have data, so a household that started
    # using the app last month doesn't see its averages cut to a third.
    active_months = {
        (d.year, d.month)
        for (d,) in db.query(Transaction.txn_date)
        .filter(Transaction.txn_date >= window_start, Transaction.txn_date <= window_end)
        .distinct()
        .all()
    }
    divisor = Decimal(max(len(active_months), 1))
    avg_income = _q(Decimal(totals.get(TxnType.income, 0)) / divisor)
    avg_expense = _q(Decimal(totals.get(TxnType.expense, 0)) / divisor)

    flagged = (
        db.query(Subscription)
        .filter(Subscription.status == SubscriptionStatus.active, Subscription.usage.in_(WASTEFUL_USAGE))
        .order_by(Subscription.amount.desc())
        .all()
    )
    cancel_items = [
        SubscriptionSavingsItem(subscription_id=s.id, name=s.name, usage=s.usage, monthly_cost=s.monthly_cost)
        for s in flagged
    ]
    subscription_savings = sum((i.monthly_cost for i in cancel_items), ZERO)
    flagged_by_category: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for s in flagged:
        if s.category_id is not None:
            flagged_by_category[s.category_id] += s.monthly_cost

    window_spend = _expense_by_category(db, window_start, window_end)
    this_month_spend = _expense_by_category(db, month_start, today)
    caps = {c.category_id: Decimal(c.monthly_limit) for c in db.query(SpendingCap).all()}
    pct = Decimal(cut_pct) / 100

    items: list[CategorySavingsItem] = []
    for cat in db.query(Category).filter(Category.type == TxnType.expense).all():
        avg = _q(window_spend.get(cat.id, ZERO) / divisor)
        this_month = this_month_spend.get(cat.id, ZERO)
        cap = caps.get(cat.id)
        if avg == 0 and this_month == 0 and cap is None:
            continue

        suggested_cap = None
        saving = ZERO
        if not cat.essential:
            baseline = max(avg - flagged_by_category.get(cat.id, ZERO), ZERO)
            suggested_cap = _q(baseline * (1 - pct))
            target = cap if cap is not None else suggested_cap
            saving = _q(max(baseline - target, ZERO))

        items.append(
            CategorySavingsItem(
                category_id=cat.id,
                category_name=cat.name,
                color=cat.color or "#64748b",
                essential=cat.essential,
                avg_monthly=avg,
                this_month=this_month,
                cap=cap,
                suggested_cap=suggested_cap,
                suggested_saving=saving,
            )
        )
    items.sort(key=lambda i: (i.essential, -i.suggested_saving, -i.avg_monthly))

    category_savings = sum((i.suggested_saving for i in items), ZERO)
    total = subscription_savings + category_savings
    return SavingsPlan(
        window_start=window_start,
        window_end=window_end,
        months=months,
        cut_pct=cut_pct,
        avg_monthly_income=avg_income,
        avg_monthly_expense=avg_expense,
        current_savings_rate=_rate(avg_income, avg_expense),
        cancel_subscriptions=cancel_items,
        categories=items,
        subscription_savings=subscription_savings,
        category_savings=category_savings,
        total_monthly_savings=total,
        total_yearly_savings=total * 12,
        projected_savings_rate=_rate(avg_income, max(avg_expense - total, ZERO)),
    )


@router.put("/caps/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def set_cap(category_id: int, body: SpendingCapIn, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    cat = db.get(Category, category_id)
    if not cat or cat.type != TxnType.expense:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense category not found")
    cap = db.query(SpendingCap).filter(SpendingCap.category_id == category_id).one_or_none()
    if cap:
        cap.monthly_limit = body.monthly_limit
    else:
        db.add(SpendingCap(category_id=category_id, monthly_limit=body.monthly_limit))
    db.commit()


@router.delete("/caps/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_cap(category_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    db.query(SpendingCap).filter(SpendingCap.category_id == category_id).delete()
    db.commit()
