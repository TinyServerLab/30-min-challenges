from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import (
    Subscription, SubscriptionStatus, SubscriptionUsage, Transaction, TxnType, User,
)
from app.schemas import (
    SubscriptionCreate, SubscriptionUpdate, SubscriptionOut, SubscriptionSummary,
    SubscriptionCandidate, TransactionOut,
)
from app.utils.billing import guess_cycle, next_due

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

UPCOMING_DAYS = 30
CANDIDATE_LOOKBACK_MONTHS = 6
WASTEFUL_USAGE = (SubscriptionUsage.rarely, SubscriptionUsage.unused)


def _get_or_404(db: Session, sub_id: int) -> Subscription:
    sub = db.get(Subscription, sub_id)
    if not sub:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found")
    return sub


def _apply_status_change(sub: Subscription, new_status: Optional[SubscriptionStatus]) -> None:
    if new_status is None or new_status == sub.status:
        return
    sub.cancelled_on = date.today() if new_status == SubscriptionStatus.cancelled else None
    sub.status = new_status


@router.get("", response_model=list[SubscriptionOut])
def list_subscriptions(
    status_filter: Optional[SubscriptionStatus] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Subscription)
    if status_filter:
        q = q.filter(Subscription.status == status_filter)
    return q.order_by(Subscription.status, Subscription.next_due_date, Subscription.name).all()


@router.get("/summary", response_model=SubscriptionSummary)
def subscription_summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    active = (
        db.query(Subscription)
        .filter(Subscription.status == SubscriptionStatus.active)
        .order_by(Subscription.next_due_date)
        .all()
    )
    horizon = date.today() + timedelta(days=UPCOMING_DAYS)
    return SubscriptionSummary(
        active_count=len(active),
        monthly_total=sum((s.monthly_cost for s in active), Decimal("0")),
        yearly_total=sum((s.yearly_cost for s in active), Decimal("0")),
        potential_monthly_savings=sum(
            (s.monthly_cost for s in active if s.usage in WASTEFUL_USAGE), Decimal("0")
        ),
        upcoming=[s for s in active if s.next_due_date <= horizon],
    )


@router.get("/candidates", response_model=list[SubscriptionCandidate])
def subscription_candidates(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Expenses that repeat with the same note, amount and category in at
    least two different months over the last six — likely subscriptions the
    household hasn't added to the manager yet. Done in Python rather than
    SQL: six months of a household's transactions is small."""
    today = date.today()
    since = today.replace(day=1) - relativedelta(months=CANDIDATE_LOOKBACK_MONTHS)
    txns = (
        db.query(Transaction)
        .filter(Transaction.type == TxnType.expense, Transaction.txn_date >= since)
        .order_by(Transaction.txn_date)
        .all()
    )
    tracked = {s.name.strip().lower() for s in db.query(Subscription.name).all()}

    groups: dict[tuple, list[Transaction]] = defaultdict(list)
    for t in txns:
        note = (t.note or "").strip()
        if not note:
            continue
        groups[(note.lower(), Decimal(t.amount), t.category_id)].append(t)

    candidates: list[SubscriptionCandidate] = []
    for (note_key, amount, category_id), rows in groups.items():
        if note_key in tracked:
            continue
        months = {(r.txn_date.year, r.txn_date.month) for r in rows}
        if len(months) < 2:
            continue
        dates = sorted(r.txn_date for r in rows)
        avg_gap = (dates[-1] - dates[0]).days / (len(dates) - 1)
        cycle = guess_cycle(avg_gap)
        last = rows[-1]
        due = next_due(last.txn_date, cycle)
        while due < today:
            due = next_due(due, cycle)
        candidates.append(
            SubscriptionCandidate(
                name=last.note.strip(),
                amount=amount,
                category_id=category_id,
                source_id=last.source_id,
                billing_cycle=cycle,
                occurrences=len(rows),
                last_date=last.txn_date,
                suggested_next_due_date=due,
            )
        )
    candidates.sort(key=lambda c: c.occurrences, reverse=True)
    return candidates


@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
def create_subscription(body: SubscriptionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = Subscription(**body.model_dump(), user_id=current_user.id)
    if sub.status == SubscriptionStatus.cancelled:
        sub.cancelled_on = date.today()
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.patch("/{sub_id}", response_model=SubscriptionOut)
def update_subscription(sub_id: int, body: SubscriptionUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    sub = _get_or_404(db, sub_id)
    changes = body.model_dump(exclude_unset=True)
    _apply_status_change(sub, changes.pop("status", None))
    for field, value in changes.items():
        setattr(sub, field, value)
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/{sub_id}/pay", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def record_payment(sub_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Log this cycle's charge as a recurring expense transaction (dated the
    current due date) and roll next_due_date forward one cycle."""
    sub = _get_or_404(db, sub_id)
    if sub.status != SubscriptionStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only active subscriptions can be marked paid")
    if sub.category_id is None or sub.source_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Set a category and payment source on this subscription before marking it paid",
        )
    txn = Transaction(
        user_id=current_user.id,
        amount=sub.amount,
        txn_date=sub.next_due_date,
        category_id=sub.category_id,
        source_id=sub.source_id,
        type=TxnType.expense,
        note=sub.name,
        recurring=True,
    )
    db.add(txn)
    sub.next_due_date = next_due(sub.next_due_date, sub.billing_cycle)
    db.commit()
    db.refresh(txn)
    return txn


@router.delete("/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscription(sub_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    sub = _get_or_404(db, sub_id)
    db.delete(sub)
    db.commit()
