from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Transaction, User, TxnType
from app.schemas import TransactionCreate, TransactionUpdate, TransactionOut

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    start: Optional[date] = None,
    end: Optional[date] = None,
    category_id: Optional[int] = None,
    source_id: Optional[int] = None,
    type: Optional[TxnType] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Transaction)
    if start:
        q = q.filter(Transaction.txn_date >= start)
    if end:
        q = q.filter(Transaction.txn_date <= end)
    if category_id:
        q = q.filter(Transaction.category_id == category_id)
    if source_id:
        q = q.filter(Transaction.source_id == source_id)
    if type:
        q = q.filter(Transaction.type == type)
    return (
        q.order_by(Transaction.txn_date.desc(), Transaction.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(body: TransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    txn = Transaction(**body.model_dump(), user_id=current_user.id)
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


@router.patch("/{txn_id}", response_model=TransactionOut)
def update_transaction(txn_id: int, body: TransactionUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    txn = db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(txn, field, value)
    db.commit()
    db.refresh(txn)
    return txn


@router.delete("/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(txn_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    txn = db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    db.delete(txn)
    db.commit()
