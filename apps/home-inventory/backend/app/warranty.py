"""Warranty date arithmetic and status classification."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from .config import get_settings


def today_local() -> date:
    return datetime.now(ZoneInfo(get_settings().tz)).date()


def add_months_inclusive(start: date, months: int) -> date:
    """12-month warranty from 10 Jan 2025 covers through 9 Jan 2026."""
    return start + relativedelta(months=months) - timedelta(days=1)


def compute_expiry(purchase_date: date, start: date | None, months: int) -> date | None:
    if months <= 0:
        return None
    return add_months_inclusive(start or purchase_date, months)


def compute_ext_expiry(mfr_expiry: date | None, purchase_date: date, ext_months: int | None) -> date | None:
    """Extended warranty normally begins the day after manufacturer warranty ends."""
    if not ext_months:
        return None
    begin = (mfr_expiry + timedelta(days=1)) if mfr_expiry else purchase_date
    return add_months_inclusive(begin, ext_months)


def effective_expiry(mfr: date | None, ext: date | None) -> date | None:
    dates = [d for d in (mfr, ext) if d]
    return max(dates) if dates else None


def classify(expiry: date | None, today: date | None = None) -> tuple[str, int | None]:
    """Return (state, days_left). state ∈ none|expired|expiring|active."""
    if not expiry:
        return "none", None
    today = today or today_local()
    days = (expiry - today).days
    if days < 0:
        return "expired", days
    if days <= get_settings().expiring_soon_days:
        return "expiring", days
    return "active", days
