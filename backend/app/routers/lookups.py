from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..auth import current_user
from ..database import get_db
from ..models import Category, Source, Transaction, User

router = APIRouter(tags=["lookups"])


# ---------------- categories ----------------
@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(
    include_archived: bool = Query(False),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = select(Category).order_by(Category.type, Category.name)
    if not include_archived:
        q = q.where(Category.is_archived.is_(False))
    return db.scalars(q).all()


@router.post("/categories", response_model=schemas.CategoryOut, status_code=201)
def create_category(body: schemas.CategoryIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    dup = db.scalar(select(Category).where(Category.type == body.type, Category.name == body.name))
    if dup:
        raise HTTPException(409, f"A {body.type} category named '{body.name}' already exists")
    cat = Category(**body.model_dump())
    db.add(cat)
    db.commit()
    return cat


@router.put("/categories/{cat_id}", response_model=schemas.CategoryOut)
def update_category(
    cat_id: int, body: schemas.CategoryIn, _: User = Depends(current_user), db: Session = Depends(get_db)
):
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    for k, v in body.model_dump().items():
        setattr(cat, k, v)
    db.commit()
    return cat


@router.delete("/categories/{cat_id}", status_code=204)
def delete_category(cat_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    in_use = db.scalar(select(func.count()).select_from(Transaction).where(Transaction.category_id == cat_id))
    if in_use:
        # keep history intact: archive instead of delete
        cat.is_archived = True
    else:
        db.delete(cat)
    db.commit()


@router.post("/categories/{cat_id}/restore", response_model=schemas.CategoryOut)
def restore_category(cat_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    cat.is_archived = False
    db.commit()
    return cat


# ---------------- sources ----------------
def _balances(db: Session) -> dict[int, Decimal]:
    signed = func.sum(
        case((Transaction.type == "income", Transaction.amount), else_=-Transaction.amount)
    )
    rows = db.execute(select(Transaction.source_id, signed).group_by(Transaction.source_id)).all()
    return {sid: Decimal(str(total or 0)) for sid, total in rows}


def _with_balance(src: Source, moves: dict[int, Decimal]) -> schemas.SourceOut:
    out = schemas.SourceOut.model_validate(src)
    if src.track_balance:
        out.balance = Decimal(str(src.opening_balance)) + moves.get(src.id, Decimal("0"))
    return out


@router.get("/sources", response_model=list[schemas.SourceOut])
def list_sources(
    include_archived: bool = Query(False),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = select(Source).order_by(Source.name)
    if not include_archived:
        q = q.where(Source.is_archived.is_(False))
    moves = _balances(db)
    return [_with_balance(s, moves) for s in db.scalars(q).all()]


@router.post("/sources", response_model=schemas.SourceOut, status_code=201)
def create_source(body: schemas.SourceIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.scalar(select(Source).where(Source.name == body.name)):
        raise HTTPException(409, f"A source named '{body.name}' already exists")
    src = Source(**body.model_dump())
    db.add(src)
    db.commit()
    return _with_balance(src, _balances(db))


@router.put("/sources/{src_id}", response_model=schemas.SourceOut)
def update_source(
    src_id: int, body: schemas.SourceIn, _: User = Depends(current_user), db: Session = Depends(get_db)
):
    src = db.get(Source, src_id)
    if not src:
        raise HTTPException(404, "Source not found")
    for k, v in body.model_dump().items():
        setattr(src, k, v)
    db.commit()
    return _with_balance(src, _balances(db))


@router.delete("/sources/{src_id}", status_code=204)
def delete_source(src_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    src = db.get(Source, src_id)
    if not src:
        raise HTTPException(404, "Source not found")
    in_use = db.scalar(select(func.count()).select_from(Transaction).where(Transaction.source_id == src_id))
    if in_use:
        src.is_archived = True
    else:
        db.delete(src)
    db.commit()


@router.post("/sources/{src_id}/restore", response_model=schemas.SourceOut)
def restore_source(src_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    src = db.get(Source, src_id)
    if not src:
        raise HTTPException(404, "Source not found")
    src.is_archived = False
    db.commit()
    return _with_balance(src, _balances(db))
