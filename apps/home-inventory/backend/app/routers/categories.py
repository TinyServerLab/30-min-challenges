from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Asset, Category, User
from ..schemas import CategoryIn, CategoryOut
from ..security import require_admin

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    counts = dict(db.execute(select(Asset.category_id, func.count()).group_by(Asset.category_id)).all())
    cats = db.scalars(select(Category).order_by(Category.sort_order, Category.name)).all()
    return [CategoryOut.model_validate(c).model_copy(update={"asset_count": counts.get(c.id, 0)}) for c in cats]


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    c = Category(**body.model_dump())
    db.add(c)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Category already exists")
    return c


@router.put("/{cat_id}", response_model=CategoryOut)
def update_category(cat_id: int, body: CategoryIn, _: User = Depends(require_admin),
                    db: Session = Depends(get_db)):
    c = db.get(Category, cat_id)
    if not c:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Category already exists")
    return c


@router.delete("/{cat_id}", status_code=204)
def delete_category(cat_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    c = db.get(Category, cat_id)
    if not c:
        raise HTTPException(404, "Not found")
    db.delete(c)       # assets keep existing, category_id -> NULL
    db.commit()
