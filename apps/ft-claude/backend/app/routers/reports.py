from datetime import date
from decimal import Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user
from app.models import Transaction, Category, TxnType, User
from app.utils.export import transactions_to_csv, transactions_to_pdf

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/monthly-summary")
def monthly_summary(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    start = date(year, month, 1)
    end = start + relativedelta(months=1) - relativedelta(days=1)

    totals = (
        db.query(Transaction.type, func.coalesce(func.sum(Transaction.amount), 0))
        .filter(Transaction.txn_date >= start, Transaction.txn_date <= end)
        .group_by(Transaction.type)
        .all()
    )
    totals_map = {t: Decimal(v) for t, v in totals}
    income = totals_map.get(TxnType.income, Decimal("0"))
    expense = totals_map.get(TxnType.expense, Decimal("0"))

    return {
        "start": start,
        "end": end,
        "total_income": income,
        "total_expense": expense,
        "net": income - expense,
    }


@router.get("/category-breakdown")
def category_breakdown(
    start: date,
    end: date,
    type: TxnType = TxnType.expense,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = (
        db.query(Category.id, Category.name, Category.color, func.coalesce(func.sum(Transaction.amount), 0))
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(Transaction.type == type, Transaction.txn_date >= start, Transaction.txn_date <= end)
        .group_by(Category.id, Category.name, Category.color)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )
    return [
        {"category_id": r[0], "category_name": r[1], "color": r[2], "total": Decimal(r[3])}
        for r in rows
    ]


def _fetch_rows(db: Session, start: date, end: date):
    return (
        db.query(Transaction)
        .options(joinedload(Transaction.category), joinedload(Transaction.source))
        .filter(Transaction.txn_date >= start, Transaction.txn_date <= end)
        .order_by(Transaction.txn_date)
        .all()
    )


@router.get("/export")
def export_transactions(
    start: date,
    end: date,
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = _fetch_rows(db, start, end)
    filename_base = f"transactions_{start.isoformat()}_to_{end.isoformat()}"

    if format == "csv":
        buf = transactions_to_csv(rows)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.csv"'},
        )

    if format == "pdf":
        buf = transactions_to_pdf(rows, start, end)
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.pdf"'},
        )

    raise HTTPException(400, "format must be csv or pdf")
