from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Investment, User
from app.schemas import InvestmentCreate, InvestmentUpdate, InvestmentOut

router = APIRouter(prefix="/investments", tags=["investments"])


@router.get("", response_model=list[InvestmentOut])
def list_investments(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Investment).order_by(Investment.entry_date.desc()).all()


@router.post("", response_model=InvestmentOut, status_code=status.HTTP_201_CREATED)
def create_investment(body: InvestmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inv = Investment(**body.model_dump(), user_id=current_user.id)
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


@router.patch("/{investment_id}", response_model=InvestmentOut)
def update_investment(investment_id: int, body: InvestmentUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    inv = db.get(Investment, investment_id)
    if not inv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investment not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(inv, field, value)
    db.commit()
    db.refresh(inv)
    return inv


@router.delete("/{investment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investment(investment_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    inv = db.get(Investment, investment_id)
    if not inv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investment not found")
    db.delete(inv)
    db.commit()
