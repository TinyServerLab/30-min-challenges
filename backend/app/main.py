import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .auth import hash_password
from .config import settings
from .database import Base, SessionLocal, engine
from .models import Category, Source, User
from .routers import auth, dashboard, lookups, reports, transactions

log = logging.getLogger("ledger")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

STATIC = Path(__file__).parent / "static"

DEFAULT_CATEGORIES = [
    ("expense", "Groceries", "🛒", "#3E7C59"),
    ("expense", "Rent / EMI", "🏠", "#8A4B38"),
    ("expense", "Utilities", "💡", "#B08A2E"),
    ("expense", "Transport", "🚌", "#4A6FA5"),
    ("expense", "Dining out", "🍽️", "#A63D40"),
    ("expense", "Health", "💊", "#6C7A54"),
    ("expense", "Education", "📚", "#5B5F97"),
    ("expense", "Shopping", "🛍️", "#9C6644"),
    ("expense", "Entertainment", "🎬", "#7D5BA6"),
    ("expense", "Family", "👨‍👩‍👧", "#3F7F8C"),
    ("expense", "Other", "•", "#6B7C75"),
    ("income", "Salary", "💼", "#1F6F5F"),
    ("income", "Freelance", "🧑‍💻", "#2E8B7A"),
    ("income", "Interest / Dividend", "📈", "#4E8F5D"),
    ("income", "Gift", "🎁", "#7C9A62"),
    ("income", "Other", "•", "#6B7C75"),
]
DEFAULT_SOURCES = [
    ("Cash", "cash", True),
    ("Bank account", "bank", True),
    ("Credit card", "credit_card", False),
    ("UPI", "upi", False),
    ("Wallet", "wallet", False),
]


def seed() -> None:
    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)) is None:
            if settings.admin_email and settings.admin_password:
                db.add(User(
                    email=settings.admin_email.lower(), name=settings.admin_name,
                    password_hash=hash_password(settings.admin_password), is_admin=True,
                ))
                log.info("Seeded admin user %s", settings.admin_email)
            else:
                log.warning("No users exist and ADMIN_EMAIL/ADMIN_PASSWORD not set — nobody can sign in. "
                            "Set them in .env or run scripts/add-user.sh")
        if db.scalar(select(Category).limit(1)) is None:
            db.add_all([Category(type=t, name=n, icon=i, color=c) for t, n, i, c in DEFAULT_CATEGORIES])
            log.info("Seeded default categories")
        if db.scalar(select(Source).limit(1)) is None:
            db.add_all([Source(name=n, kind=k, track_balance=b) for n, k, b in DEFAULT_SOURCES])
            log.info("Seeded default payment sources")
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    seed()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")

for r in (auth.router, lookups.router, transactions.router, dashboard.router, reports.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/api/config", include_in_schema=False)
def config():
    return {"app_name": settings.app_name, "currency_symbol": settings.currency_symbol}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/docs"):
        return resp  # swagger UI loads its assets from a CDN
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    )
    return resp


@app.exception_handler(404)
async def spa_fallback(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return FileResponse(STATIC / "index.html")


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
