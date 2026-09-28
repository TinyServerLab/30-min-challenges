"""Warranty expiry reminders: daily digest via email (SMTP) and/or ntfy push.

Tiers come from REMINDER_DAYS (default 30,7,0). For each warranty only the *closest* tier
reached is sent, and each (asset, warranty, expiry, tier, channel) is logged so nothing is
sent twice — which also means a Pi that was off at 9am catches up on the next run.
"""
import logging
import smtplib
import ssl
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage
from html import escape

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal
from .models import Asset, ReminderLog, User
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


def channels() -> list[str]:
    ch = []
    if settings.smtp_host and settings.smtp_from:
        ch.append("email")
    if settings.ntfy_url:
        ch.append("ntfy")
    return ch


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


def _asset_url(a: Asset) -> str:
    return f"{settings.public_url.rstrip('/')}/assets/{a.id}"


def send_email(to: list[str], subject: str, text_body: str, html_body: str | None = None) -> None:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, settings.smtp_from, ", ".join(to)
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    ctx = ssl.create_default_context()
    if settings.smtp_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx, timeout=30) as s:
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password or "")
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as s:
            if settings.smtp_starttls:
                s.starttls(context=ctx)
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password or "")
            s.send_message(msg)


def send_ntfy(title: str, body: str, click: str | None = None, priority: str = "default") -> None:
    headers = {"Title": title.encode("utf-8").decode("latin-1", "ignore"), "Priority": priority,
               "Tags": "warning"}
    if click:
        headers["Click"] = click
    if settings.ntfy_token:
        headers["Authorization"] = f"Bearer {settings.ntfy_token}"
    httpx.post(settings.ntfy_url, content=body.encode("utf-8"), headers=headers, timeout=20).raise_for_status()


def _recipients(db: Session) -> list[str]:
    return [u.email for u in db.scalars(select(User).where(User.is_active, User.notify_email)).all()]


def _render(items: list[Due]) -> tuple[str, str, str]:
    n = len(items)
    subject = f"Warranty reminder: {n} item{'s' if n != 1 else ''} expiring soon"
    lines, rows = [], []
    for d in items:
        label = d.asset.name + (f" ({d.asset.brand})" if d.asset.brand else "")
        kind = "Extended warranty" if d.warranty_type == "extended" else "Warranty"
        lines.append(f"• {label} — {kind} ends {_when(d.days_left)} ({d.expiry:%d %b %Y})\n  {_asset_url(d.asset)}")
        rows.append(f"<tr><td style='padding:6px 10px'><a href='{escape(_asset_url(d.asset))}'>{escape(label)}</a></td>"
                    f"<td style='padding:6px 10px'>{kind}</td>"
                    f"<td style='padding:6px 10px'><b>{_when(d.days_left)}</b> · {d.expiry:%d %b %Y}</td></tr>")
    text_body = "These warranties are about to end:\n\n" + "\n".join(lines) + \
        "\n\nTip: raise any pending service request before the warranty ends.\n"
    html_body = ("<div style='font-family:system-ui,sans-serif'><h3>Warranties ending soon</h3>"
                 "<table style='border-collapse:collapse;border:1px solid #e5e7eb'>" + "".join(rows) +
                 "</table><p style='color:#6b7280'>Raise any pending service request before the warranty ends.</p></div>")
    return subject, text_body, html_body


def run_reminders(force_today: date | None = None) -> dict:
    """Entry point for the scheduler (and the admin 'run now' button)."""
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
            for ch in channels():
                pending = [d for d in due if not _already_sent(db, d, ch)]
                if not pending:
                    result["sent"][ch] = 0
                    continue
                subject, text_body, html_body = _render(pending)
                try:
                    if ch == "email":
                        to = _recipients(db)
                        if not to:
                            continue
                        send_email(to, subject, text_body, html_body)
                    elif ch == "ntfy":
                        urgent = any(d.days_left <= 7 for d in pending)
                        send_ntfy(subject, text_body, settings.public_url, "high" if urgent else "default")
                    for d in pending:
                        db.add(ReminderLog(asset_id=d.asset.id, warranty_type=d.warranty_type,
                                           expiry_date=d.expiry, days_before=d.tier, channel=ch))
                    db.commit()
                    result["sent"][ch] = len(pending)
                except Exception as e:
                    db.rollback()
                    log.exception("reminder via %s failed", ch)
                    result["errors"].append(f"{ch}: {e}")
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
