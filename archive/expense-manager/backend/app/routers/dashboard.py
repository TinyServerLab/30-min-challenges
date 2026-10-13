from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import schemas
from ..auth import current_user
from ..database import get_db
from ..models import Category, Investment, InvestmentEntry, Transaction, User

router = APIRouter(tags=["dashboard"])

D0 = Decimal("0")


def month_bounds(d: date) -> tuple[date, date]:
    start = d.replace(day=1)
    nxt = (start.replace(year=start.year + 1, month=1) if start.month == 12
           else start.replace(month=start.month + 1))
    return start, nxt


def category_slices(db: Session, start: date, end: date, tx_type: str) -> list[schemas.CategorySlice]:
    rows = db.execute(
        select(Category.id, Category.name, Category.icon, Category.color,
               func.sum(Transaction.amount), func.count())
        .join(Transaction, Transaction.category_id == Category.id)
        .where(Transaction.type == tx_type, Transaction.date >= start, Transaction.date <= end)
        .group_by(Category.id)
        .order_by(func.sum(Transaction.amount).desc())
    ).all()
    return [
        schemas.CategorySlice(category_id=r[0], name=r[1], icon=r[2], color=r[3],
                              total=Decimal(str(r[4])), count=r[5])
        for r in rows
    ]


def totals(db: Session, start: date, end: date) -> tuple[Decimal, Decimal]:
    rows = db.execute(
        select(Transaction.type, func.sum(Transaction.amount))
        .where(Transaction.date >= start, Transaction.date <= end)
        .group_by(Transaction.type)
    ).all()
    t = {k: Decimal(str(v or 0)) for k, v in rows}
    return t.get("income", D0), t.get("expense", D0)


def investment_summary(db: Session) -> tuple[Decimal, Decimal]:
    """(total contributed, latest marked value) across non-archived holdings."""
    holdings = db.scalars(
        select(Investment).where(Investment.is_archived.is_(False)).options(selectinload(Investment.entries))
    ).all()
    invested = value = D0
    for h in holdings:
        inv = sum((Decimal(str(e.contribution)) for e in h.entries), D0)
        valued = [e for e in h.entries if e.current_value is not None]
        cur = Decimal(str(valued[-1].current_value)) if valued else inv
        invested += inv
        value += cur
    return invested, value


@router.get("/dashboard", response_model=schemas.DashboardOut)
def dashboard(
    start: date | None = None,
    end: date | None = None,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    if start is None or end is None:
        s, nxt = month_bounds(today)
        start, end = s, nxt.fromordinal(nxt.toordinal() - 1)
    if end < start:
        raise HTTPException(400, "End date is before start date")

    income, expense = totals(db, start, end)

    # trailing 12-month trend ending at `end`'s month; cumulative net runs from all history
    trend_start_month = (end.year * 12 + end.month - 1) - 11
    ts_year, ts_month = divmod(trend_start_month, 12)
    trend_start = date(ts_year, ts_month + 1, 1)

    before = db.execute(
        select(Transaction.type, func.sum(Transaction.amount)).where(Transaction.date < trend_start)
        .group_by(Transaction.type)
    ).all()
    b = {k: Decimal(str(v or 0)) for k, v in before}
    cumulative = b.get("income", D0) - b.get("expense", D0)

    rows = db.execute(
        select(Transaction.date, Transaction.type, Transaction.amount)
        .where(Transaction.date >= trend_start, Transaction.date <= end)
    ).all()
    buckets: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"income": D0, "expense": D0})
    for d, t, amt in rows:
        buckets[d.strftime("%Y-%m")][t] += Decimal(str(amt))

    trend: list[schemas.MonthPoint] = []
    y, m = trend_start.year, trend_start.month
    for _ in range(12):
        key = f"{y:04d}-{m:02d}"
        inc, exp = buckets[key]["income"], buckets[key]["expense"]
        cumulative += inc - exp
        trend.append(schemas.MonthPoint(month=key, income=inc, expense=exp, net=inc - exp, cumulative=cumulative))
        m += 1
        if m == 13:
            m, y = 1, y + 1

    invested, value = investment_summary(db)
    return schemas.DashboardOut(
        start=start, end=end, income=income, expense=expense, net=income - expense,
        expense_by_category=category_slices(db, start, end, "expense"),
        income_by_category=category_slices(db, start, end, "income"),
        trend=trend, investments_invested=invested, investments_value=value,
    )


# ---------------- investments ----------------
def inv_out(h: Investment) -> schemas.InvestmentOut:
    invested = sum((Decimal(str(e.contribution)) for e in h.entries), D0)
    valued = [e for e in h.entries if e.current_value is not None]
    return schemas.InvestmentOut(
        id=h.id, name=h.name, kind=h.kind, note=h.note, is_archived=h.is_archived,
        invested=invested,
        current_value=Decimal(str(valued[-1].current_value)) if valued else None,
        last_valued=valued[-1].date if valued else None,
        entries=[schemas.InvestmentEntryOut.model_validate(e) for e in h.entries],
    )


def _get_inv(db: Session, inv_id: int) -> Investment:
    h = db.scalar(select(Investment).where(Investment.id == inv_id).options(selectinload(Investment.entries)))
    if not h:
        raise HTTPException(404, "Investment not found")
    return h


@router.get("/investments", response_model=list[schemas.InvestmentOut])
def list_investments(
    include_archived: bool = Query(False), _: User = Depends(current_user), db: Session = Depends(get_db)
):
    q = select(Investment).options(selectinload(Investment.entries)).order_by(Investment.kind, Investment.name)
    if not include_archived:
        q = q.where(Investment.is_archived.is_(False))
    return [inv_out(h) for h in db.scalars(q).all()]


@router.post("/investments", response_model=schemas.InvestmentOut, status_code=201)
def create_investment(body: schemas.InvestmentIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    h = Investment(**body.model_dump())
    db.add(h)
    db.commit()
    return inv_out(_get_inv(db, h.id))


@router.put("/investments/{inv_id}", response_model=schemas.InvestmentOut)
def update_investment(
    inv_id: int, body: schemas.InvestmentIn, _: User = Depends(current_user), db: Session = Depends(get_db)
):
    h = _get_inv(db, inv_id)
    for k, v in body.model_dump().items():
        setattr(h, k, v)
    db.commit()
    return inv_out(_get_inv(db, inv_id))


@router.delete("/investments/{inv_id}", status_code=204)
def delete_investment(inv_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    h = _get_inv(db, inv_id)
    if h.entries:
        h.is_archived = True
    else:
        db.delete(h)
    db.commit()


@router.post("/investments/{inv_id}/entries", response_model=schemas.InvestmentOut, status_code=201)
def add_entry(
    inv_id: int, body: schemas.InvestmentEntryIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    h = _get_inv(db, inv_id)
    h.entries.append(InvestmentEntry(**body.model_dump(), created_by=user.id))
    db.commit()
    return inv_out(_get_inv(db, inv_id))


@router.delete("/investments/{inv_id}/entries/{entry_id}", response_model=schemas.InvestmentOut)
def delete_entry(inv_id: int, entry_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    e = db.get(InvestmentEntry, entry_id)
    if not e or e.investment_id != inv_id:
        raise HTTPException(404, "Entry not found")
    db.delete(e)
    db.commit()
    return inv_out(_get_inv(db, inv_id))
