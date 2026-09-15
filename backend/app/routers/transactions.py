from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..auth import current_user
from ..database import get_db
from ..models import Category, Source, Transaction, User

router = APIRouter(prefix="/transactions", tags=["transactions"])


def to_out(t: Transaction) -> schemas.TransactionOut:
    return schemas.TransactionOut(
        id=t.id,
        type=t.type,
        amount=t.amount,
        date=t.date,
        category_id=t.category_id,
        source_id=t.source_id,
        note=t.note,
        is_recurring=t.is_recurring,
        created_by=t.created_by,
        created_at=t.created_at,
        category_name=t.category.name,
        category_icon=t.category.icon,
        category_color=t.category.color,
        source_name=t.source.name,
        user_name=t.user.name,
    )


def _validate_refs(db: Session, body: schemas.TransactionIn) -> None:
    cat = db.get(Category, body.category_id)
    if not cat:
        raise HTTPException(400, "Category not found")
    if cat.type != body.type:
        raise HTTPException(400, f"'{cat.name}' is a {cat.type} category, not {body.type}")
    if not db.get(Source, body.source_id):
        raise HTTPException(400, "Payment source not found")


@router.get("", response_model=schemas.Paged)
def list_transactions(
    start: date | None = None,
    end: date | None = None,
    type: str | None = Query(None, pattern="^(expense|income)$"),
    category_id: int | None = None,
    source_id: int | None = None,
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Transaction)
    if start:
        stmt = stmt.where(Transaction.date >= start)
    if end:
        stmt = stmt.where(Transaction.date <= end)
    if type:
        stmt = stmt.where(Transaction.type == type)
    if category_id:
        stmt = stmt.where(Transaction.category_id == category_id)
    if source_id:
        stmt = stmt.where(Transaction.source_id == source_id)
    if q:
        stmt = stmt.where(Transaction.note.ilike(f"%{q}%"))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Transaction.date.desc(), Transaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return schemas.Paged(items=[to_out(t) for t in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=schemas.TransactionOut, status_code=201)
def create_transaction(
    body: schemas.TransactionIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _validate_refs(db, body)
    t = Transaction(**body.model_dump(), created_by=user.id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return to_out(t)


@router.put("/{tx_id}", response_model=schemas.TransactionOut)
def update_transaction(
    tx_id: int, body: schemas.TransactionIn, _: User = Depends(current_user), db: Session = Depends(get_db)
):
    t = db.get(Transaction, tx_id)
    if not t:
        raise HTTPException(404, "Transaction not found")
    _validate_refs(db, body)
    for k, v in body.model_dump().items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return to_out(t)


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Transaction, tx_id)
    if not t:
        raise HTTPException(404, "Transaction not found")
    db.delete(t)
    db.commit()
