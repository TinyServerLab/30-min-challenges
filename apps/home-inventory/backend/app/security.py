"""Password hashing, server-side sessions, auth dependencies, login throttling."""
import hashlib
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import AuditLog, User, UserSession

settings = get_settings()
# Argon2id with modest memory so it stays fast on a Raspberry Pi 5.
_ph = PasswordHasher(time_cost=3, memory_cost=32 * 1024, parallelism=2)
_DUMMY_HASH = _ph.hash("timing-equaliser")


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw: str, hashed: str | None) -> bool:
    try:
        return _ph.verify(hashed or _DUMMY_HASH, pw) and hashed is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_strength(pw: str) -> None:
    if len(pw) < 10:
        raise HTTPException(400, "Password must be at least 10 characters")
    classes = sum([any(c.islower() for c in pw), any(c.isupper() for c in pw),
                   any(c.isdigit() for c in pw), any(not c.isalnum() for c in pw)])
    if classes < 2:
        raise HTTPException(400, "Mix letters with digits, capitals or symbols")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


# ------------------------------------------------------------------ throttling
class LoginThrottle:
    """In-memory failed-login counter per (ip) and per (identifier)."""

    def __init__(self) -> None:
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _window(self) -> float:
        return settings.login_lockout_minutes * 60

    def blocked(self, *keys: str) -> bool:
        cutoff = time.time() - self._window()
        with self._lock:
            for k in keys:
                hits = [t for t in self._fails.get(k, []) if t > cutoff]
                self._fails[k] = hits
                limit = settings.login_max_attempts * (4 if k.startswith("ip:") else 1)
                if len(hits) >= limit:
                    return True
        return False

    def fail(self, *keys: str) -> None:
        with self._lock:
            for k in keys:
                self._fails.setdefault(k, []).append(time.time())

    def reset(self, *keys: str) -> None:
        with self._lock:
            for k in keys:
                self._fails.pop(k, None)


throttle = LoginThrottle()


# -------------------------------------------------------------------- sessions
def create_session(db: Session, user: User, request: Request, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    expires = now_utc() + timedelta(days=settings.session_days)
    db.add(UserSession(user_id=user.id, token_hash=_token_hash(token), expires_at=expires,
                       user_agent=(request.headers.get("user-agent") or "")[:300],
                       ip_address=client_ip(request)))
    # housekeeping: drop expired sessions
    db.execute(delete(UserSession).where(UserSession.expires_at < now_utc()))
    response.set_cookie(settings.cookie_name, token, max_age=settings.session_days * 86400,
                        path=settings.cookie_path, secure=settings.cookie_secure,
                        httponly=True, samesite="lax")


def destroy_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(settings.cookie_name)
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == _token_hash(token)))
    response.delete_cookie(settings.cookie_name, path=settings.cookie_path,
                           secure=settings.cookie_secure, httponly=True, samesite="lax")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == _token_hash(token)))
    now = now_utc()
    if not sess or sess.expires_at < now or not sess.user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    # sliding expiry, but write at most every 10 minutes
    if (now - sess.last_seen_at) > timedelta(minutes=10):
        sess.last_seen_at = now
        sess.expires_at = now + timedelta(days=settings.session_days)
        db.commit()
    request.state.user = sess.user
    return sess.user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user


def audit(db: Session, user_id: int | None, action: str, entity: str | None = None,
          entity_id: int | None = None, **detail) -> None:
    db.add(AuditLog(user_id=user_id, action=action, entity=entity, entity_id=entity_id,
                    detail=detail or None))
