from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import PaymentSource
from app.schemas import SourceCreate, SourceUpdate, SourceOut

router = APIRouter(prefix="/sources", tags=["payment-sources"])


@router.get("", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(PaymentSource).order_by(PaymentSource.name).all()


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(body: SourceCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    src = PaymentSource(**body.model_dump())
    db.add(src)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A payment source with that name already exists")
    db.refresh(src)
    return src


@router.patch("/{source_id}", response_model=SourceOut)
def update_source(source_id: int, body: SourceUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    src = db.get(PaymentSource, source_id)
    if not src:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment source not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(src, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A payment source with that name already exists")
    db.refresh(src)
    return src


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    src = db.get(PaymentSource, source_id)
    if not src:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment source not found")
    if src.transactions:
        raise HTTPException(status.HTTP_409_CONFLICT, "Source has transactions — reassign or delete them first")
    db.delete(src)
    db.commit()
