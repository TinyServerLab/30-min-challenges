from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..db import get_db
from ..models import Asset, Category, ServiceRecord
from ..warranty import today_local
from .assets import EFFECTIVE, asset_out

router = APIRouter(tags=["dashboard"])
settings = get_settings()
CURRENT = Asset.status.in_(["active", "in_repair"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    today = today_local()
    soon = today + timedelta(days=settings.expiring_soon_days)
    year_start = today.replace(month=1, day=1)

    def count(*conds):
        return db.scalar(select(func.count(Asset.id)).where(*conds)) or 0

    def total(col, *conds):
        return db.scalar(select(func.coalesce(func.sum(col), 0)).where(*conds)) or Decimal("0")

    upcoming = db.scalars(select(Asset).options(selectinload(Asset.attachments))
                          .where(CURRENT, EFFECTIVE >= today, EFFECTIVE <= today + timedelta(days=90))
                          .order_by(EFFECTIVE.asc()).limit(8)).all()
    recent_expired = db.scalars(select(Asset).options(selectinload(Asset.attachments))
                                .where(CURRENT, EFFECTIVE < today, EFFECTIVE >= today - timedelta(days=60))
                                .order_by(EFFECTIVE.desc()).limit(5)).all()
    recent = db.scalars(select(Asset).options(selectinload(Asset.attachments))
                        .order_by(Asset.created_at.desc()).limit(5)).all()

    by_cat = db.execute(
        select(Category.name, Category.color, func.count(Asset.id), func.coalesce(func.sum(Asset.purchase_price), 0))
        .select_from(Asset).join(Category, Asset.category_id == Category.id, isouter=True)
        .where(CURRENT).group_by(Category.name, Category.color)
        .order_by(func.sum(Asset.purchase_price).desc())).all()

    return {
        "today": today,
        "expiring_window_days": settings.expiring_soon_days,
        "counts": {
            "assets": count(CURRENT),
            "under_warranty": count(CURRENT, EFFECTIVE >= today),
            "expiring_soon": count(CURRENT, EFFECTIVE >= today, EFFECTIVE <= soon),
            "expired": count(CURRENT, EFFECTIVE < today),
            "no_warranty": count(CURRENT, EFFECTIVE.is_(None)),
            "in_repair": count(Asset.status == "in_repair"),
        },
        "value": {
            "total": total(Asset.purchase_price, CURRENT),
            "this_year": total(Asset.purchase_price, Asset.purchase_date >= year_start),
            "service_this_year": total(ServiceRecord.cost, ServiceRecord.service_date >= year_start),
            "covered": total(Asset.purchase_price, CURRENT, EFFECTIVE >= today),
        },
        "by_category": [{"name": n or "Uncategorised", "color": c or "#94a3b8", "count": k, "value": v}
                        for n, c, k, v in by_cat],
        "upcoming": [asset_out(a) for a in upcoming],
        "recently_expired": [asset_out(a) for a in recent_expired],
        "recent": [asset_out(a) for a in recent],
    }


@router.get("/reports/spending")
def spending(year: int | None = None, db: Session = Depends(get_db)):
    today = today_local()
    year = year or today.year
    yr = func.extract("year", Asset.purchase_date)
    years = [int(y) for y in db.scalars(select(yr).group_by(yr).order_by(yr.desc())).all()]
    if year not in years:
        years = sorted(set(years) | {year}, reverse=True)

    y0, y1 = date(year, 1, 1), date(year, 12, 31)
    in_year = and_(Asset.purchase_date >= y0, Asset.purchase_date <= y1)
    mo = func.extract("month", Asset.purchase_date)
    monthly = {int(m): v for m, v in db.execute(select(mo, func.sum(Asset.purchase_price)).where(in_year).group_by(mo))}
    smo = func.extract("month", ServiceRecord.service_date)
    s_in_year = and_(ServiceRecord.service_date >= y0, ServiceRecord.service_date <= y1)
    svc_monthly = {int(m): v for m, v in db.execute(select(smo, func.sum(ServiceRecord.cost)).where(s_in_year).group_by(smo))}

    by_cat = db.execute(
        select(Category.name, Category.color, func.count(Asset.id), func.sum(Asset.purchase_price))
        .select_from(Asset).join(Category, Asset.category_id == Category.id, isouter=True)
        .where(in_year).group_by(Category.name, Category.color)
        .order_by(func.sum(Asset.purchase_price).desc())).all()
    vcol = func.coalesce(Asset.vendor, "Unknown").label("vendor_name")
    by_vendor = db.execute(
        select(vcol, func.count(Asset.id), func.sum(Asset.purchase_price))
        .where(in_year).group_by(vcol)
        .order_by(func.sum(Asset.purchase_price).desc()).limit(10)).all()

    yearly = db.execute(select(yr, func.sum(Asset.purchase_price), func.count(Asset.id))
                        .group_by(yr).order_by(yr)).all()
    top = db.scalars(select(Asset).options(selectinload(Asset.attachments)).where(in_year)
                     .order_by(Asset.purchase_price.desc()).limit(10)).all()

    purchases = sum((v or 0 for v in monthly.values()), Decimal("0"))
    services = sum((v or 0 for v in svc_monthly.values()), Decimal("0"))
    return {
        "year": year, "years": years,
        "totals": {"purchases": purchases, "services": services, "total": purchases + services,
                   "count": db.scalar(select(func.count(Asset.id)).where(in_year)) or 0},
        "monthly": [{"month": m, "purchases": monthly.get(m, 0) or 0, "services": svc_monthly.get(m, 0) or 0}
                    for m in range(1, 13)],
        "by_category": [{"name": n or "Uncategorised", "color": c or "#94a3b8", "count": k, "value": v}
                        for n, c, k, v in by_cat],
        "by_vendor": [{"name": n, "count": k, "value": v} for n, k, v in by_vendor],
        "yearly": [{"year": int(y), "value": v, "count": k} for y, v, k in yearly],
        "top_purchases": [asset_out(a) for a in top],
    }
