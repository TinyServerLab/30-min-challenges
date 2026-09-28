from datetime import date
from decimal import Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Transaction, Category, Investment, TxnType, User
from app.schemas import DashboardSummary, CategoryBreakdownItem, SavingsTrendPoint, InvestmentTrendPoint

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _month_bounds(d: date) -> tuple[date, date]:
    start = d.replace(day=1)
    end = start + relativedelta(months=1) - relativedelta(days=1)
    return start, end


@router.get("/summary", response_model=DashboardSummary)
def summary(
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not start or not end:
        start, end = _month_bounds(date.today())

    totals = (
        db.query(Transaction.type, func.coalesce(func.sum(Transaction.amount), 0))
        .filter(Transaction.txn_date >= start, Transaction.txn_date <= end)
        .group_by(Transaction.type)
        .all()
    )
    totals_map = {t: Decimal(v) for t, v in totals}
    total_income = totals_map.get(TxnType.income, Decimal("0"))
    total_expense = totals_map.get(TxnType.expense, Decimal("0"))

    breakdown_rows = (
        db.query(Category.id, Category.name, Category.color, func.coalesce(func.sum(Transaction.amount), 0))
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.type == TxnType.expense,
            Transaction.txn_date >= start,
            Transaction.txn_date <= end,
        )
        .group_by(Category.id, Category.name, Category.color)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )
    breakdown = [
        CategoryBreakdownItem(category_id=r[0], category_name=r[1], color=r[2], total=Decimal(r[3]))
        for r in breakdown_rows
    ]

    return DashboardSummary(
        start=start,
        end=end,
        total_income=total_income,
        total_expense=total_expense,
        net=total_income - total_expense,
        expense_by_category=breakdown,
    )


@router.get("/savings-trend", response_model=list[SavingsTrendPoint])
def savings_trend(
    months: int = Query(12, ge=1, le=60),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Cumulative cash savings (income − expense) by month, from transactions
    only. Investments are intentionally excluded here — see
    /dashboard/investment-trend for that, plotted on its own timeline rather
    than merged into this one."""
    today = date.today()
    range_start = today.replace(day=1) - relativedelta(months=months - 1)

    monthly_net = (
        db.query(
            func.to_char(Transaction.txn_date, "YYYY-MM").label("month"),
            func.coalesce(func.sum(
                case((Transaction.type == TxnType.income, Transaction.amount), else_=0)
            ), 0).label("income"),
            func.coalesce(func.sum(
                case((Transaction.type == TxnType.expense, Transaction.amount), else_=0)
            ), 0).label("expense"),
        )
        .filter(Transaction.txn_date >= range_start)
        .group_by("month")
        .order_by("month")
        .all()
    )
    net_by_month = {row.month: Decimal(row.income) - Decimal(row.expense) for row in monthly_net}

    points: list[SavingsTrendPoint] = []
    cumulative = Decimal("0")
    cursor = range_start
    for _i in range(months):
        key = cursor.strftime("%Y-%m")
        cumulative += net_by_month.get(key, Decimal("0"))
        points.append(SavingsTrendPoint(month=key, cumulative_savings=cumulative))
        cursor = cursor + relativedelta(months=1)
    return points


@router.get("/investment-trend", response_model=list[InvestmentTrendPoint])
def investment_trend(
    months: int = Query(12, ge=1, le=60),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Investment growth on its own timeline, keyed off each entry's
    entry_date — cumulative amount contributed vs. cumulative current value,
    as of each month. Kept separate from the cash savings trend rather than
    merged into a single net-worth line."""
    today = date.today()
    range_start = today.replace(day=1) - relativedelta(months=months - 1)

    monthly_inv = (
        db.query(
            func.to_char(Investment.entry_date, "YYYY-MM").label("month"),
            func.coalesce(func.sum(Investment.contribution_amount), 0).label("contribution"),
            func.coalesce(func.sum(Investment.current_value), 0).label("current_value"),
        )
        .group_by("month")
        .order_by("month")
        .all()
    )
    contribution_by_month = {row.month: Decimal(row.contribution) for row in monthly_inv}
    value_by_month = {row.month: Decimal(row.current_value) for row in monthly_inv}

    # Anything entered before the visible window still counts toward the
    # starting cumulative totals.
    earliest_key = range_start.strftime("%Y-%m")
    cumulative_contribution = sum(
        (v for k, v in contribution_by_month.items() if k < earliest_key), Decimal("0")
    )
    cumulative_value = sum(
        (v for k, v in value_by_month.items() if k < earliest_key), Decimal("0")
    )

    points: list[InvestmentTrendPoint] = []
    cursor = range_start
    for _i in range(months):
        key = cursor.strftime("%Y-%m")
        cumulative_contribution += contribution_by_month.get(key, Decimal("0"))
        cumulative_value += value_by_month.get(key, Decimal("0"))
        points.append(
            InvestmentTrendPoint(
                month=key,
                cumulative_contribution=cumulative_contribution,
                cumulative_current_value=cumulative_value,
            )
        )
        cursor = cursor + relativedelta(months=1)
    return points
