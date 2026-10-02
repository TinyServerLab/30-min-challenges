"""Application entry point.

Everything — SPA, static assets and /api — is served under BASE_PATH (default /inventory),
so Caddy can forward the prefix untouched:  handle /inventory* { reverse_proxy home-inventory:8000 }
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text

from .config import get_settings
from .db import SessionLocal, engine
from .migrate import run_migrations
from .models import Attachment, User
from .routers import assets, attachments, auth, categories, dashboard, notifications, users
from .security import get_current_user, hash_password
from .storage import delete_files

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def bootstrap_admin() -> None:
    with SessionLocal() as db:
        if db.scalar(select(func.count(User.id))):
            return
        if not (settings.admin_email and settings.admin_password):
            log.warning("No users exist. Set ADMIN_EMAIL/ADMIN_PASSWORD or run: "
                        "docker compose exec app python -m app.cli create-user --admin")
            return
        db.add(User(email=settings.admin_email.lower(), display_name=settings.admin_name,
                    password_hash=hash_password(settings.admin_password), is_admin=True))
        db.commit()
        log.info("Created bootstrap admin %s — remove ADMIN_PASSWORD from .env now", settings.admin_email)


def purge_draft_uploads() -> None:
    """Uploads never attached to an asset (abandoned forms) are removed after 24h."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    with SessionLocal() as db:
        drafts = db.scalars(select(Attachment).where(Attachment.asset_id.is_(None),
                                                     Attachment.created_at < cutoff)).all()
        for a in drafts:
            delete_files(a.stored_path, a.thumb_path)
            db.delete(a)
        db.commit()
        if drafts:
            log.info("purged %d abandoned draft uploads", len(drafts))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    applied = run_migrations()
    if applied:
        log.info("Migrations applied: %s", applied)
    bootstrap_admin()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    from .reminders import start_scheduler
    sched = start_scheduler()
    sched.add_job(purge_draft_uploads, "interval", hours=6, id="purge-drafts",
                  next_run_time=datetime.now(timezone.utc) + timedelta(minutes=1))
    yield
    sched.shutdown(wait=False)
    engine.dispose()


# ----------------------------------------------------------------- inner app (under BASE_PATH)
app = FastAPI(title="Home Asset + Warranty",
              docs_url="/api/docs" if settings.enable_api_docs else None,
              redoc_url=None,
              openapi_url="/api/openapi.json" if settings.enable_api_docs else None)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    # CSRF defence in depth (on top of SameSite=Lax cookie): state-changing API calls must
    # carry a custom header, which browsers never add on cross-site form posts.
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and "/api/" in request.url.path:
        if request.headers.get("x-requested-with") != "fetch":
            return JSONResponse({"detail": "Missing X-Requested-With header"}, status_code=403)
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("Permissions-Policy", "camera=(self), geolocation=(), microphone=()")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; frame-src 'self' blob:; object-src 'self' blob:; frame-ancestors 'self'; base-uri 'self'")
    return resp


@app.get("/api/health", include_in_schema=False)
def health():
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/config", include_in_schema=False)
def public_config():
    return {"base_path": settings.base_path, "currency": settings.default_currency,
            "max_upload_mb": settings.max_upload_mb}


api = APIRouter(prefix="/api")
api.include_router(auth.router)                                  # login is public; others check inside
protected = [Depends(get_current_user)]
api.include_router(users.router, dependencies=protected)
api.include_router(categories.router, dependencies=protected)
api.include_router(assets.router, dependencies=protected)
api.include_router(attachments.router, dependencies=protected)
api.include_router(dashboard.router, dependencies=protected)
api.include_router(notifications.router, dependencies=protected)
app.include_router(api)


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def api_404(rest: str):
    return JSONResponse({"detail": "Not found"}, status_code=404)


# ---------------------------------------------------------------------- SPA
_index_cache: str | None = None


def _index_html() -> str:
    global _index_cache
    if _index_cache is None:
        idx = STATIC_DIR / "index.html"
        if not idx.exists():
            return "<h1>Frontend not built</h1><p>Run <code>npm run build</code> in /frontend.</p>"
        # The frontend is built with relative asset URLs; <base> pins them to BASE_PATH at runtime,
        # so the same image works under /inventory or any other prefix.
        _index_cache = idx.read_text(encoding="utf-8").replace(
            '<base href="/" />', f'<base href="{settings.base_path}/" />', 1)
    return _index_cache


# Vite emits hashed bundles to /_app (not /assets, which is an SPA route)
if (STATIC_DIR / "_app").exists():
    app.mount("/_app", StaticFiles(directory=STATIC_DIR / "_app"), name="static-assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    f = (STATIC_DIR / path).resolve()
    if path and f.is_file() and STATIC_DIR.resolve() in f.parents and f.name != "index.html":
        return FileResponse(f)                     # favicon, manifest, icons
    return HTMLResponse(_index_html(), headers={"Cache-Control": "no-cache"})


# ------------------------------------------------------------------ outer app (prefix)
if settings.base_path:
    root = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @root.get("/", include_in_schema=False)
    @root.get(settings.base_path, include_in_schema=False)
    def _to_base():
        return RedirectResponse(f"{settings.base_path}/", status_code=308)

    @root.get("/healthz", include_in_schema=False)
    def _healthz():
        return health()

    root.mount(settings.base_path, app)
    application = root
else:
    app.router.lifespan_context = lifespan
    application = app
