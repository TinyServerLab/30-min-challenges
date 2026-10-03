"""Warranty expiry reminders: one daily digest per enabled channel
(email, ntfy, Discord, Telegram — switched on/off in Settings → Notifications).

Tiers come from REMINDER_DAYS (default 30,7,0). For each warranty only the *closest* tier
reached is sent, and each (asset, warranty, expiry, tier, channel) is logged so nothing is
sent twice — which also means a Pi that was off at 9am catches up on the next run, and a
channel switched on later still receives what is currently due.
"""
import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import notify
from .config import get_settings
from .db import SessionLocal
from .models import Asset, ReminderLog
from .warranty import today_local

log = logging.getLogger("reminders")
settings = get_settings()
LOCK_KEY = 874_200_202


@dataclass
class Due:
    asset: Asset
    warranty_type: str      # manufacturer | extended
    expiry: date
    days_left: int
    tier: int


def find_due(db: Session, today: date) -> list[Due]:
    tiers = settings.reminder_day_list  # e.g. [30, 7, 0]
    if not tiers:
        return []
    horizon = max(tiers)
    out: list[Due] = []
    assets = db.scalars(select(Asset).where(Asset.status.in_(["active", "in_repair"]))).all()
    for a in assets:
        for wtype, exp in (("manufacturer", a.warranty_expiry_date), ("extended", a.ext_warranty_expiry_date)):
            if not exp:
                continue
            left = (exp - today).days
            if left < 0 or left > horizon:
                continue
            tier = min(t for t in tiers if t >= left)   # closest tier already reached
            out.append(Due(a, wtype, exp, left, tier))
    out.sort(key=lambda d: d.days_left)
    return out


def _already_sent(db: Session, d: Due, channel: str) -> bool:
    return db.scalar(select(ReminderLog.id).where(
        ReminderLog.asset_id == d.asset.id, ReminderLog.warranty_type == d.warranty_type,
        ReminderLog.expiry_date == d.expiry, ReminderLog.days_before == d.tier,
        ReminderLog.channel == channel)) is not None


def _when(n: int) -> str:
    return "today" if n == 0 else ("tomorrow" if n == 1 else f"in {n} days")


def asset_url(asset_id: int) -> str:
    return f"{settings.public_url.rstrip('/')}/assets/{asset_id}"


def build_message(items: list[Due]) -> notify.Message:
    n = len(items)
    lines = []
    for d in items:
        label = d.asset.name + (f" ({d.asset.brand})" if d.asset.brand else "")
        kind = "Extended warranty" if d.warranty_type == "extended" else "Warranty"
        lines.append(notify.Line(label=label, detail=f"{kind} ends {_when(d.days_left)} ({d.expiry:%d %b %Y})",
                                 url=asset_url(d.asset.id)))
    return notify.Message(
        title=f"Warranty reminder: {n} item{'s' if n != 1 else ''} expiring soon",
        intro="These warranties are about to end:",
        lines=lines,
        footer="Tip: raise any pending service request before the warranty ends.",
        urgent=any(d.days_left <= 7 for d in items),
    )


def run_reminders(force_today: date | None = None) -> dict:
    """Entry point for the scheduler (and the admin 'send due reminders now' button)."""
    today = force_today or today_local()
    result = {"date": str(today), "due": 0, "sent": {}, "errors": []}
    with SessionLocal() as db:
        got = db.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY}).scalar()
        if not got:
            result["errors"].append("another reminder run is in progress")
            return result
        try:
            due = find_due(db, today)
            result["due"] = len(due)
            for ch, cfg in notify.active_channels(db):
                pending = [d for d in due if not _already_sent(db, d, ch)]
                if not pending:
                    result["sent"][ch] = 0
                    continue
                try:
                    notify.deliver(db, ch, cfg, build_message(pending))
                    for d in pending:
                        db.add(ReminderLog(asset_id=d.asset.id, warranty_type=d.warranty_type,
                                           expiry_date=d.expiry, days_before=d.tier, channel=ch))
                    notify.record(db, ch, True)
                    db.commit()
                    result["sent"][ch] = len(pending)
                except Exception as e:
                    db.rollback()
                    msg = str(e) if isinstance(e, notify.NotifyError) else f"{type(e).__name__}: {e}"
                    log.warning("reminder via %s failed: %s", ch, msg)
                    notify.record(db, ch, False, msg)
                    db.commit()
                    result["errors"].append(f"{notify.LABELS.get(ch, ch)}: {msg}")
            db.commit()
        finally:
            db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
            db.commit()
    log.info("reminder run: %s", result)
    return result


def start_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    sched = BackgroundScheduler(timezone=settings.tz)
    sched.add_job(run_reminders, CronTrigger(hour=settings.reminder_hour, minute=settings.reminder_minute,
                                             timezone=settings.tz),
                  id="warranty-reminders", misfire_grace_time=6 * 3600, coalesce=True)
    sched.start()
    return sched
