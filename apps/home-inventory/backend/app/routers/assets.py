import csv
import io
from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..db import get_db
from ..models import Asset, Attachment, Category, ServiceRecord, User
from ..schemas import AssetDetail, AssetIn, AssetOut, AssetPage, AttachmentOut, ServiceIn, ServiceOut
from ..security import audit, get_current_user
from ..storage import delete_files
from ..warranty import classify, compute_expiry, compute_ext_expiry, effective_expiry, today_local

router = APIRouter(tags=["assets"])
settings = get_settings()

EFFECTIVE = func.greatest(Asset.warranty_expiry_date, Asset.ext_warranty_expiry_date)


def attachment_out(a: Attachment) -> AttachmentOut:
    return AttachmentOut.model_validate(a).model_copy(update={"has_thumb": bool(a.thumb_path)})


def asset_out(a: Asset, detail: bool = False):
    eff = effective_expiry(a.warranty_expiry_date, a.ext_warranty_expiry_date)
    state, days = classify(eff)
    thumb = next((x.id for x in a.attachments if x.thumb_path and x.kind == "photo"), None) \
        or next((x.id for x in a.attachments if x.thumb_path), None)
    extra = {
        "category_name": a.category.name if a.category else None,
        "category_color": a.category.color if a.category else None,
        "category_icon": a.category.icon if a.category else None,
        "effective_expiry_date": eff, "warranty_state": state, "days_left": days,
        "attachment_count": len(a.attachments), "thumb_attachment_id": thumb,
    }
    if detail:
        extra["attachments"] = [attachment_out(x) for x in a.attachments]
        extra["services"] = [ServiceOut.model_validate(s) for s in a.services]
        extra["service_cost_total"] = sum((s.cost for s in a.services), Decimal("0"))
        return AssetDetail.model_validate(a).model_copy(update=extra)
    return AssetOut.model_validate(a).model_copy(update=extra)


def apply_payload(a: Asset, body: AssetIn) -> None:
    data = body.model_dump(exclude={"attachment_ids"})
    for k, v in data.items():
        setattr(a, k, v)
    if not body.warranty_expiry_manual or not body.warranty_expiry_date:
        a.warranty_expiry_manual = False
        a.warranty_expiry_date = compute_expiry(body.purchase_date, body.warranty_start_date, body.warranty_months)
    if body.ext_warranty_months:
        a.ext_warranty_expiry_date = compute_ext_expiry(a.warranty_expiry_date, body.purchase_date,
                                                        body.ext_warranty_months)
    # else: ext_warranty_expiry_date is whatever the user typed (or None)


def _load(db: Session, asset_id: int) -> Asset:
    a = db.scalar(select(Asset).options(selectinload(Asset.attachments), selectinload(Asset.services))
                  .where(Asset.id == asset_id))
    if not a:
        raise HTTPException(404, "Asset not found")
    return a


def _filtered(q, category_id, status, warranty, year):
    today = today_local()
    soon = today + timedelta(days=settings.expiring_soon_days)
    conds = []
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(Asset.name.ilike(like), Asset.brand.ilike(like), Asset.model.ilike(like),
                         Asset.serial_number.ilike(like), Asset.vendor.ilike(like),
                         Asset.invoice_number.ilike(like), Asset.location.ilike(like),
                         Asset.owner_name.ilike(like), Asset.notes.ilike(like)))
    if category_id:
        conds.append(Asset.category_id == category_id)
    if status == "current":
        conds.append(Asset.status.in_(["active", "in_repair"]))
    elif status and status != "all":
        conds.append(Asset.status == status)
    if warranty == "active":
        conds.append(EFFECTIVE >= today)
    elif warranty == "expiring":
        conds.append(and_(EFFECTIVE >= today, EFFECTIVE <= soon))
    elif warranty == "expired":
        conds.append(EFFECTIVE < today)
    elif warranty == "none":
        conds.append(EFFECTIVE.is_(None))
    if year:
        conds.append(func.extract("year", Asset.purchase_date) == year)
    return conds


SORTS = {
    "purchase_date": Asset.purchase_date, "name": func.lower(Asset.name),
    "price": Asset.purchase_price, "expiry": EFFECTIVE, "created": Asset.created_at,
}


@router.get("/assets", response_model=AssetPage)
def list_assets(q: str | None = None, category_id: int | None = None, status: str | None = "current",
                warranty: str | None = Query(None, pattern="^(active|expiring|expired|none)$"),
                year: int | None = None, sort: str = "purchase_date", order: str = "desc",
                page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
                db: Session = Depends(get_db)):
    conds = _filtered(q, category_id, status, warranty, year)
    total, value = db.execute(select(func.count(Asset.id), func.coalesce(func.sum(Asset.purchase_price), 0))
                              .where(*conds)).one()
    col = SORTS.get(sort, Asset.purchase_date)
    ordering = (asc(col).nulls_last() if order == "asc" else desc(col).nulls_last(), desc(Asset.id))
    rows = db.scalars(select(Asset).options(selectinload(Asset.attachments)).where(*conds)
                      .order_by(*ordering).offset((page - 1) * page_size).limit(page_size)).all()
    return AssetPage(items=[asset_out(a) for a in rows], total=total, page=page, page_size=page_size,
                     total_value=value)


@router.get("/assets/export.csv")
def export_csv(q: str | None = None, category_id: int | None = None, status: str | None = None,
               warranty: str | None = None, year: int | None = None, db: Session = Depends(get_db)):
    rows = db.scalars(select(Asset).options(selectinload(Asset.attachments))
                      .where(*_filtered(q, category_id, status, warranty, year))
                      .order_by(Asset.purchase_date.desc())).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ID", "Name", "Brand", "Model", "Serial", "Category", "Location", "Owner", "Purchase date",
                "Price", "Currency", "Vendor", "Invoice no", "Warranty months", "Warranty expiry",
                "Ext. warranty provider", "Ext. warranty expiry", "Effective expiry", "Warranty state",
                "Status", "Notes"])
    for a in rows:
        o = asset_out(a)
        w.writerow([a.id, a.name, a.brand, a.model, a.serial_number, o.category_name, a.location, a.owner_name,
                    a.purchase_date, a.purchase_price, a.currency, a.vendor, a.invoice_number, a.warranty_months,
                    a.warranty_expiry_date, a.ext_warranty_provider, a.ext_warranty_expiry_date,
                    o.effective_expiry_date, o.warranty_state, a.status, a.notes])
    data = "﻿" + buf.getvalue()   # BOM so Excel opens UTF-8 (₹) correctly
    fname = f"home-assets-{today_local():%Y%m%d}.csv"
    return StreamingResponse(iter([data]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/assets/suggestions")
def suggestions(db: Session = Depends(get_db)):
    """Distinct values for form autocomplete."""
    def distinct(col):
        return [r for r in db.scalars(select(col).where(col.is_not(None)).group_by(col)
                                      .order_by(func.count().desc()).limit(50)).all()]
    return {"brands": distinct(Asset.brand), "vendors": distinct(Asset.vendor),
            "locations": distinct(Asset.location), "owners": distinct(Asset.owner_name),
            "payment_methods": distinct(Asset.payment_method)}


@router.get("/assets/{asset_id}", response_model=AssetDetail)
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    return asset_out(_load(db, asset_id), detail=True)


def _check_category(db: Session, cid: int | None):
    if cid and not db.get(Category, cid):
        raise HTTPException(400, "Unknown category")


@router.post("/assets", response_model=AssetDetail, status_code=201)
def create_asset(body: AssetIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_category(db, body.category_id)
    a = Asset(created_by=user.id, updated_by=user.id)
    apply_payload(a, body)
    db.add(a)
    db.flush()
    if body.attachment_ids:
        for att in db.scalars(select(Attachment).where(Attachment.id.in_(body.attachment_ids),
                                                       Attachment.asset_id.is_(None))).all():
            att.asset_id = a.id
    audit(db, user.id, "asset.create", "asset", a.id, name=a.name)
    db.commit()
    return asset_out(_load(db, a.id), detail=True)


@router.put("/assets/{asset_id}", response_model=AssetDetail)
def update_asset(asset_id: int, body: AssetIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    a = _load(db, asset_id)
    _check_category(db, body.category_id)
    apply_payload(a, body)
    a.updated_by = user.id
    if body.attachment_ids:
        for att in db.scalars(select(Attachment).where(Attachment.id.in_(body.attachment_ids),
                                                       Attachment.asset_id.is_(None))).all():
            att.asset_id = a.id
    audit(db, user.id, "asset.update", "asset", a.id)
    db.commit()
    db.expire_all()
    return asset_out(_load(db, a.id), detail=True)


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(asset_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = _load(db, asset_id)
    files = [(x.stored_path, x.thumb_path) for x in a.attachments]
    audit(db, user.id, "asset.delete", "asset", a.id, name=a.name)
    db.delete(a)
    db.commit()
    for sp, tp in files:
        delete_files(sp, tp)


# ------------------------------------------------------------------ service records
@router.post("/assets/{asset_id}/services", response_model=ServiceOut, status_code=201)
def add_service(asset_id: int, body: ServiceIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    if not db.get(Asset, asset_id):
        raise HTTPException(404, "Asset not found")
    s = ServiceRecord(asset_id=asset_id, created_by=user.id, **body.model_dump())
    db.add(s)
    db.commit()
    return s


@router.put("/services/{service_id}", response_model=ServiceOut)
def update_service(service_id: int, body: ServiceIn, db: Session = Depends(get_db)):
    s = db.get(ServiceRecord, service_id)
    if not s:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    db.commit()
    return s


@router.delete("/services/{service_id}", status_code=204)
def delete_service(service_id: int, db: Session = Depends(get_db)):
    s = db.get(ServiceRecord, service_id)
    if not s:
        raise HTTPException(404, "Not found")
    db.delete(s)
    db.commit()
