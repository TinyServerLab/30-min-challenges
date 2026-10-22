from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.config import settings
from app.routers import (
    auth, categories, sources, transactions, investments, dashboard, reports,
    subscriptions, savings,
)

app = FastAPI(title="Personal Finance Tracker", version="1.0.0")

if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(investments.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(subscriptions.router, prefix="/api")
app.include_router(savings.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve the built React frontend (copied into the image at /app/static by
# the Dockerfile's frontend build stage). Falls back to index.html for any
# non-API path so client-side routing works on a hard refresh.
STATIC_DIR = Path("/app/static")
_index_cache: str | None = None


def _index_html() -> str:
    """index.html with <base href> pointed at BASE_PATH. The frontend is
    built with relative asset URLs and derives its API/router prefix from
    <base>, so one image works at the site root or under /finance."""
    global _index_cache
    if _index_cache is None:
        _index_cache = (STATIC_DIR / "index.html").read_text(encoding="utf-8").replace(
            '<base href="/" />', f'<base href="{settings.base_path}/" />', 1
        )
    return _index_cache


if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa_catch_all(full_path: str):
        candidate = (STATIC_DIR / full_path).resolve()
        if full_path and candidate.is_file() and STATIC_DIR.resolve() in candidate.parents and candidate.name != "index.html":
            return FileResponse(candidate)
        return HTMLResponse(_index_html(), headers={"Cache-Control": "no-cache"})


# Behind a path-routing proxy (Caddy `handle /finance* { reverse_proxy ... }`)
# the prefix is forwarded untouched, so mount the whole app under it. The
# container healthcheck still hits /api/health at the root.
if settings.base_path:
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @application.get("/", include_in_schema=False)
    @application.get(settings.base_path, include_in_schema=False)
    def _to_base():
        return RedirectResponse(f"{settings.base_path}/", status_code=308)

    application.get("/api/health", include_in_schema=False)(health)
    application.mount(settings.base_path, app)
else:
    application = app
