"""Settings → Notifications: per-channel switches, Discord/Telegram setup, tests, manual run."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import notify
from ..config import get_settings
from ..db import get_db
from ..models import User
from ..reminders import find_due, run_reminders
from ..security import audit, get_current_user, require_admin
from ..warranty import today_local

router = APIRouter(prefix="/notifications", tags=["notifications"])
settings = get_settings()

EDITABLE_KEYS = {"discord": {"webhook_url", "mention"}, "telegram": {"bot_token", "chat_id", "chat_title"}}


class ChannelUpdate(BaseModel):
    enabled: bool | None = None
    # key missing = keep, "" or null = clear, value = set. Masked values (with ••••) are ignored.
    config: dict[str, str | int | None] | None = None


class TelegramLookup(BaseModel):
    bot_token: str | None = Field(default=None, max_length=100)


def _check(ch: str) -> None:
    if ch not in notify.CHANNELS:
        raise HTTPException(404, "Unknown channel")


def _validate(ch: str, key: str, value: str) -> str:
    if ch == "discord" and key == "webhook_url" and not notify.DISCORD_WEBHOOK_RE.match(value):
        raise HTTPException(400, "That is not a Discord webhook URL. It looks like "
                                 "https://discord.com/api/webhooks/123…/abc…")
    if ch == "discord" and key == "mention" and not notify.DISCORD_MENTION_RE.match(value):
        raise HTTPException(400, "Mention must be @here, @everyone, <@userId> or <@&roleId>")
    if ch == "telegram" and key == "bot_token" and not notify.TG_TOKEN_RE.match(value):
        raise HTTPException(400, "That is not a Telegram bot token. It looks like 123456789:AAH…")
    if ch == "telegram" and key == "chat_id" and not notify.TG_CHAT_RE.match(value):
        raise HTTPException(400, "Chat ID must be a number (groups start with -100…) or @channelname")
    if ch == "telegram" and key == "chat_title":
        value = value[:100]
    return value


@router.get("/status")
def status(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    active = [ch for ch, _cfg in notify.active_channels(db)]
    db.commit()
    return {"channels": active, "reminder_days": settings.reminder_day_list,
            "reminder_time": f"{settings.reminder_hour:02d}:{settings.reminder_minute:02d}",
            "timezone": settings.tz, "due_now": len(find_due(db, today_local()))}


@router.get("/channels")
def list_channels(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = notify.load_channels(db)
    db.commit()
    return [notify.public_view(rows[ch], user.is_admin) for ch in notify.CHANNELS]


@router.put("/channels/{ch}")
def update_channel(ch: str, body: ChannelUpdate, db: Session = Depends(get_db),
                   admin: User = Depends(require_admin)):
    _check(ch)
    row = notify.load_channels(db)[ch]
    cfg = dict(row.config or {})
    changed = []
    if body.config is not None:
        allowed = EDITABLE_KEYS.get(ch)
        if not allowed:
            raise HTTPException(400, f"{notify.LABELS[ch]} is configured in the .env file")
        for key, raw in body.config.items():
            if key not in allowed:
                raise HTTPException(400, f"Unknown setting '{key}'")
            value = "" if raw is None else str(raw).strip()
            if "••••" in value:              # masked placeholder echoed back → unchanged
                continue
            if value == "":
                if cfg.pop(key, None) is not None:
                    changed.append(key)
            elif cfg.get(key) != value:
                cfg[key] = _validate(ch, key, value)
                changed.append(key)
        if "chat_id" in changed and "chat_title" not in body.config:
            cfg.pop("chat_title", None)
        row.config = cfg
        if changed:
            row.last_ok = row.last_error = row.last_attempt_at = None

    problem = notify.setup_problem(ch, cfg)
    if body.enabled is True and problem:
        raise HTTPException(400, f"Can't switch on {notify.LABELS[ch]} yet: {problem}")
    if body.enabled is not None:
        row.enabled = body.enabled
    elif problem and row.enabled and ch in notify.MANAGED_IN_APP:
        row.enabled = False                  # settings were cleared → switch off
    row.updated_by = admin.id
    audit(db, admin.id, "notifications.update", "channel", None, channel=ch, enabled=row.enabled,
          changed=",".join(changed) or None)
    db.commit()
    db.refresh(row)
    return notify.public_view(row, True)


@router.post("/channels/{ch}/test")
async def test_channel(ch: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    _check(ch)
    row = notify.load_channels(db)[ch]
    cfg = row.config or {}
    problem = notify.setup_problem(ch, cfg)
    if problem:
        raise HTTPException(400, problem)
    msg = notify.Message(
        kind="test",
        title="Home Inventory: test notification",
        intro=f"It works! Warranty expiry reminders will arrive here every day at "
              f"{settings.reminder_hour:02d}:{settings.reminder_minute:02d} when something is due.",
        lines=[notify.Line(label="Example: Samsung Refrigerator", detail="Warranty ends in 7 days",
                           url=settings.public_url)],
        footer=f"Test sent by {admin.display_name}",
    )
    try:
        await run_in_threadpool(notify.deliver, db, ch, cfg, msg, [admin.email] if ch == "email" else None)
    except notify.NotifyError as e:
        notify.record(db, ch, False, str(e))
        db.commit()
        return {"ok": False, "detail": str(e)}
    notify.record(db, ch, True)
    db.commit()
    return {"ok": True, "detail": f"Test sent via {notify.LABELS[ch]}"
            + (f" to {admin.email}" if ch == "email" else "")}


@router.post("/telegram/chats")
async def telegram_chats(body: TelegramLookup, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Validate the bot token and list chats that have messaged the bot, so the user can pick one."""
    token = (body.bot_token or "").strip()
    if not token or "••••" in token:
        token = (notify.load_channels(db)["telegram"].config or {}).get("bot_token") or ""
    if not notify.TG_TOKEN_RE.match(token):
        raise HTTPException(400, "Enter the bot token from @BotFather first")
    try:
        bot = await run_in_threadpool(notify.telegram_bot_info, token)
        chats = await run_in_threadpool(notify.telegram_recent_chats, token)
    except notify.NotifyError as e:
        raise HTTPException(400, str(e))
    return {"bot": bot, "chats": chats}


@router.post("/run")
def run_now(_: User = Depends(require_admin)):
    return run_reminders()
