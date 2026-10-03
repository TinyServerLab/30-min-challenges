"""Notification channels: email (SMTP), ntfy, Discord (webhook) and Telegram (bot).

Each channel has a row in `notification_channels` with an on/off switch. Email and ntfy read
their connection details from .env; Discord and Telegram are configured in the app.

Secrets (Discord webhook URL, Telegram bot token) are never sent back to the browser in full
and never written to logs — httpx request logging is silenced because those URLs carry them.
"""
import logging
import re
import smtplib
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import NotificationChannel, User

log = logging.getLogger("notify")
logging.getLogger("httpx").setLevel(logging.WARNING)      # request lines contain the bot token
logging.getLogger("httpcore").setLevel(logging.WARNING)
settings = get_settings()

CHANNELS = ("email", "ntfy", "discord", "telegram")
LABELS = {"email": "Email", "ntfy": "ntfy push", "discord": "Discord", "telegram": "Telegram"}
MANAGED_IN_APP = {"discord", "telegram"}
SECRET_KEYS = {"discord": {"webhook_url"}, "telegram": {"bot_token"}}

DISCORD_WEBHOOK_RE = re.compile(
    r"^https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api/webhooks/\d{5,25}/[A-Za-z0-9_-]{20,200}$")
DISCORD_MENTION_RE = re.compile(r"^(@everyone|@here|<@&?\d{5,25}>)$")
TG_TOKEN_RE = re.compile(r"^\d{5,15}:[A-Za-z0-9_-]{30,64}$")
TG_CHAT_RE = re.compile(r"^(-?\d{1,20}|@[A-Za-z][A-Za-z0-9_]{4,31})$")

# One shared client. Tests swap it for a client with an httpx.MockTransport.
http = httpx.Client(timeout=20, headers={"User-Agent": "HomeInventory/1.0"})


class NotifyError(Exception):
    """A delivery problem with a message that is safe to show in the UI."""


# ------------------------------------------------------------------ message model
@dataclass
class Line:
    label: str          # "Samsung Refrigerator (Samsung)"
    detail: str         # "Warranty ends in 7 days (09 Oct 2026)"
    url: str | None = None


@dataclass
class Message:
    title: str
    intro: str = ""
    lines: list[Line] = field(default_factory=list)
    footer: str = ""
    urgent: bool = False
    kind: str = "reminder"   # reminder | test

    def plain(self) -> str:
        out = [self.intro] if self.intro else []
        if self.lines:
            out.append("\n".join(f"• {ln.label} — {ln.detail}" + (f"\n  {ln.url}" if ln.url else "")
                                 for ln in self.lines))
        if self.footer:
            out.append(self.footer)
        return "\n\n".join(out)


def _chunks(lines: list[str], limit: int) -> list[list[str]]:
    """Group lines so each group's joined length stays under `limit`."""
    out, cur, size = [], [], 0
    for ln in lines:
        ln = ln[: limit - 10]
        if cur and size + len(ln) + 1 > limit:
            out.append(cur)
            cur, size = [], 0
        cur.append(ln)
        size += len(ln) + 1
    if cur:
        out.append(cur)
    return out or [[]]


def _scrub(text: str, *secrets: str | None) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "•••")
    return text[:500]


def _http_error(service: str, e: Exception, *secrets) -> NotifyError:
    if isinstance(e, httpx.TimeoutException):
        return NotifyError(f"{service} did not respond (timeout). Check the Pi's internet connection.")
    if isinstance(e, httpx.ConnectError):
        return NotifyError(f"Could not connect to {service}. Check the Pi's internet / DNS.")
    return NotifyError(_scrub(f"{service}: {type(e).__name__}: {e}", *secrets))


# ------------------------------------------------------------------------ email
def email_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def send_email(to: list[str], subject: str, text_body: str, html_body: str | None = None) -> None:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, settings.smtp_from, ", ".join(to)
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    ctx = ssl.create_default_context()
    try:
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
    except (smtplib.SMTPException, OSError) as e:
        raise NotifyError(_scrub(f"Email: {e}", settings.smtp_password)) from e


def _email_html(m: Message) -> str:
    rows = []
    for ln in m.lines:
        label = escape(ln.label)
        if ln.url:
            label = f'<a href="{escape(ln.url, quote=True)}">{label}</a>'
        rows.append(f"<tr><td style='padding:6px 10px'>{label}</td>"
                    f"<td style='padding:6px 10px'>{escape(ln.detail)}</td></tr>")
    table = f"<table style='border-collapse:collapse;border:1px solid #e5e7eb'>{''.join(rows)}</table>" if rows else ""
    return (f"<div style='font-family:system-ui,sans-serif'><h3>{escape(m.title)}</h3>"
            f"<p>{escape(m.intro)}</p>{table}<p style='color:#6b7280'>{escape(m.footer)}</p></div>")


# ------------------------------------------------------------------------- ntfy
def ntfy_configured() -> bool:
    return bool(settings.ntfy_url)


def send_ntfy(title: str, body: str, click: str | None = None, priority: str = "default") -> None:
    headers = {"Title": title.encode("utf-8").decode("latin-1", "ignore"), "Priority": priority,
               "Tags": "warning"}
    if click:
        headers["Click"] = click
    if settings.ntfy_token:
        headers["Authorization"] = f"Bearer {settings.ntfy_token}"
    try:
        r = http.post(settings.ntfy_url, content=body.encode("utf-8"), headers=headers)
    except httpx.HTTPError as e:
        raise _http_error("ntfy", e, settings.ntfy_token) from e
    if r.status_code >= 300:
        raise NotifyError(f"ntfy: HTTP {r.status_code} {r.text[:200]}")


# ---------------------------------------------------------------------- Discord
DISCORD_COLORS = {"urgent": 0xE34948, "reminder": 0xEDA100, "test": 0x0F766E}


def _discord_post(url: str, payload: dict) -> None:
    for attempt in range(2):
        try:
            r = http.post(url, json=payload, params={"wait": "true"})
        except httpx.HTTPError as e:
            raise _http_error("Discord", e, url) from e
        if r.status_code == 429 and attempt == 0:                 # rate limited: wait once
            try:
                wait = float(r.json().get("retry_after", 1))
            except Exception:
                wait = 1.0
            time.sleep(min(wait, 5))
            continue
        if r.status_code < 300:
            return
        try:
            detail = r.json().get("message", "")
        except Exception:
            detail = r.text[:200]
        hint = {401: " — the webhook token is wrong", 404: " — the webhook was deleted or the URL is wrong"}
        raise NotifyError(f"Discord: {detail or 'error'} (HTTP {r.status_code}){hint.get(r.status_code, '')}")


def send_discord(cfg: dict, m: Message) -> None:
    url = cfg.get("webhook_url")
    if not url:
        raise NotifyError("Discord webhook URL is not set")
    color = DISCORD_COLORS["test" if m.kind == "test" else ("urgent" if m.urgent else "reminder")]
    lines = [f"**{f'[{_md(ln.label)}]({ln.url})' if ln.url else _md(ln.label)}**\n{_md(ln.detail)}" for ln in m.lines]
    groups = _chunks(lines, 3800)
    mention = (cfg.get("mention") or "").strip()
    for i, group in enumerate(groups):
        desc = "\n\n".join(([_md(m.intro)] if m.intro and i == 0 else []) + group)
        embed = {"title": m.title if i == 0 else f"{m.title} (contd.)", "description": desc[:4096], "color": color}
        if m.footer and i == len(groups) - 1:
            embed["footer"] = {"text": m.footer[:2048]}
        payload = {
            "username": "Home Inventory",
            "embeds": [embed],
            # never let an asset name like "@everyone" ping people; only the configured mention may
            "allowed_mentions": {"parse": ["everyone", "roles", "users"]} if mention and i == 0 else {"parse": []},
        }
        if mention and i == 0:
            payload["content"] = mention
        _discord_post(url, payload)


def _md(s: str) -> str:
    """Escape Discord markdown in user-entered text."""
    return re.sub(r"([\\*_~`|>\[\]()])", r"\\\1", s or "")


# --------------------------------------------------------------------- Telegram
TG_HINTS = {
    "chat not found": "Chat not found — send any message to the bot first (or add it to the group), then use “Find my chat”.",
    "bot was blocked by the user": "The bot was blocked — unblock it in Telegram.",
    "bot is not a member": "The bot is not in that group/channel — add it first.",
    "not enough rights": "The bot needs permission to post in that channel.",
    "Unauthorized": "The bot token is invalid — copy it again from @BotFather.",
    "terminated by other getUpdates": "Another program is reading this bot's updates; stop it and try again.",
    "can't use getUpdates method while webhook is active": "This bot has a webhook set; type the chat ID manually instead.",
}


def _tg_call(token: str, method: str, payload: dict | None = None) -> dict | list:
    url = f"{settings.telegram_api_base.rstrip('/')}/bot{token}/{method}"
    for attempt in range(2):
        try:
            r = http.post(url, json=payload or {})
        except httpx.HTTPError as e:
            raise _http_error("Telegram", e, token) from e
        try:
            data = r.json()
        except Exception:
            raise NotifyError(f"Telegram: unexpected reply (HTTP {r.status_code})")
        if data.get("ok"):
            return data.get("result")
        retry = (data.get("parameters") or {}).get("retry_after")
        if r.status_code == 429 and retry and attempt == 0:
            time.sleep(min(float(retry), 5))
            continue
        desc = _scrub(str(data.get("description") or f"HTTP {r.status_code}"), token)
        hint = next((h for k, h in TG_HINTS.items() if k.lower() in desc.lower()), "")
        raise NotifyError(f"Telegram: {desc}" + (f". {hint}" if hint else ""))
    raise NotifyError("Telegram: rate limited, try again later")


def send_telegram(cfg: dict, m: Message) -> None:
    token, chat = cfg.get("bot_token"), cfg.get("chat_id")
    if not (token and chat):
        raise NotifyError("Telegram bot token and chat ID are required")
    icon = "🧪" if m.kind == "test" else ("🔴" if m.urgent else "🟡")
    head = f"{icon} <b>{escape(m.title)}</b>" + (f"\n{escape(m.intro)}" if m.intro else "")
    lines = [(f'• <a href="{escape(ln.url, quote=True)}">{escape(ln.label)}</a>' if ln.url else f"• {escape(ln.label)}")
             + f"\n   {escape(ln.detail)}" for ln in m.lines]
    tail = f"<i>{escape(m.footer)}</i>" if m.footer else ""
    groups = _chunks(lines, 3600)
    for i, group in enumerate(groups):
        parts = ([head] if i == 0 else []) + ["\n".join(group)] + ([tail] if i == len(groups) - 1 and tail else [])
        _tg_call(token, "sendMessage", {
            "chat_id": chat, "text": "\n\n".join(p for p in parts if p)[:4096], "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True}, "disable_web_page_preview": True,
        })


def telegram_bot_info(token: str) -> dict:
    me = _tg_call(token, "getMe")
    return {"username": me.get("username"), "name": me.get("first_name")}


def telegram_recent_chats(token: str) -> list[dict]:
    """Chats that recently messaged the bot (from getUpdates; does not consume them)."""
    updates = _tg_call(token, "getUpdates", {"limit": 100, "timeout": 0})
    chats: dict[int, dict] = {}
    for u in updates or []:
        for key in ("message", "edited_message", "channel_post", "my_chat_member", "chat_member"):
            c = (u.get(key) or {}).get("chat")
            if not c:
                continue
            title = c.get("title") or " ".join(x for x in (c.get("first_name"), c.get("last_name")) if x) \
                or (f"@{c['username']}" if c.get("username") else str(c["id"]))
            chats[c["id"]] = {"id": str(c["id"]), "title": title, "type": c.get("type", "?"),
                              "username": c.get("username")}
    return list(chats.values())[::-1]


# ---------------------------------------------------------------- channel state
def load_channels(db: Session) -> dict[str, NotificationChannel]:
    rows = {r.channel: r for r in db.scalars(select(NotificationChannel)).all()}
    for ch in CHANNELS:                       # self-heal if a row was deleted by hand
        if ch not in rows:
            rows[ch] = NotificationChannel(channel=ch, enabled=ch in ("email", "ntfy"), config={})
            db.add(rows[ch])
    db.flush()
    return rows


def setup_problem(ch: str, cfg: dict) -> str | None:
    """None when the channel has everything it needs, else what is missing."""
    if ch == "email":
        return None if email_configured() else "Set SMTP_HOST and SMTP_FROM in the .env file"
    if ch == "ntfy":
        return None if ntfy_configured() else "Set NTFY_URL in the .env file"
    if ch == "discord":
        return None if cfg.get("webhook_url") else "Paste a Discord webhook URL"
    if ch == "telegram":
        if not cfg.get("bot_token"):
            return "Add the bot token from @BotFather"
        return None if cfg.get("chat_id") else "Choose the chat to send to"
    return "Unknown channel"


def active_channels(db: Session) -> list[tuple[str, dict]]:
    rows = load_channels(db)
    return [(ch, rows[ch].config or {}) for ch in CHANNELS
            if rows[ch].enabled and setup_problem(ch, rows[ch].config or {}) is None]


def email_recipients(db: Session) -> list[str]:
    return [u.email for u in db.scalars(select(User).where(User.is_active, User.notify_email)).all()]


def deliver(db: Session, ch: str, cfg: dict, m: Message, to: list[str] | None = None) -> None:
    """Send one message on one channel. Raises NotifyError with a UI-safe message."""
    if ch == "email":
        to = to if to is not None else email_recipients(db)
        if not to:
            raise NotifyError("No family member has email reminders switched on")
        send_email(to, m.title, m.plain(), _email_html(m))
    elif ch == "ntfy":
        send_ntfy(m.title, m.plain(), settings.public_url, "high" if m.urgent else "default")
    elif ch == "discord":
        send_discord(cfg, m)
    elif ch == "telegram":
        send_telegram(cfg, m)
    else:
        raise NotifyError(f"Unknown channel {ch}")


def record(db: Session, ch: str, ok: bool, error: str | None = None) -> None:
    row = db.get(NotificationChannel, ch)
    if row:
        row.last_attempt_at = datetime.now(timezone.utc)
        row.last_ok = ok
        row.last_error = None if ok else (error or "failed")[:500]


# ---------------------------------------------------------------- UI helpers
def mask(ch: str, key: str, value: str | None) -> str | None:
    if not value:
        return None
    if ch == "discord" and key == "webhook_url":
        m = re.match(r"^(https://[^/]+/api/webhooks/\d+)/(.+)$", value)
        return f"{m.group(1)}/••••{m.group(2)[-4:]}" if m else "••••"
    if ch == "telegram" and key == "bot_token":
        bot_id, _, rest = value.partition(":")
        return f"{bot_id}:••••{rest[-4:]}"
    return "••••"


def public_view(row: NotificationChannel, admin: bool) -> dict:
    cfg = row.config or {}
    out = {
        "channel": row.channel, "label": LABELS[row.channel], "enabled": row.enabled,
        "managed_in_app": row.channel in MANAGED_IN_APP,
        "problem": setup_problem(row.channel, cfg),
        "last_attempt_at": row.last_attempt_at, "last_ok": row.last_ok,
        "last_error": row.last_error if admin else None,
    }
    if admin and row.channel in MANAGED_IN_APP:
        secrets = SECRET_KEYS.get(row.channel, set())
        out["config"] = {k: (mask(row.channel, k, v) if k in secrets else v) for k, v in cfg.items()}
        out["has_secret"] = {k: bool(cfg.get(k)) for k in secrets}
    if row.channel == "email":
        out["info"] = f"From {settings.smtp_from}" if email_configured() else None
    if row.channel == "ntfy":
        out["info"] = re.sub(r"(https?://[^/]+/).*", r"\1…", settings.ntfy_url) if ntfy_configured() else None
    return out
