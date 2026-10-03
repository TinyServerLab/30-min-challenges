"""Tiny, transparent migration runner.

Applies backend/migrations/NNNN_*.sql in order, each in its own transaction,
recording applied versions in `schema_migrations`. A PostgreSQL advisory lock
makes concurrent starts safe. Only ever touches the app's own database.
"""
import logging
from pathlib import Path

from sqlalchemy import text

from .db import engine

log = logging.getLogger("migrate")
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
LOCK_KEY = 874_200_101  # arbitrary, app-specific


def run_migrations() -> list[str]:
    applied_now: list[str] = []
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": LOCK_KEY})
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version    TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"""))
            conn.commit()
            done = {r[0] for r in conn.execute(text("SELECT version FROM schema_migrations"))}
            for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
                version = f.stem
                if version in done:
                    continue
                log.info("Applying migration %s", version)
                sql = f.read_text(encoding="utf-8")
                raw = conn.connection.dbapi_connection  # psycopg connection: multi-statement OK
                with raw.cursor() as cur:
                    cur.execute(sql)
                    cur.execute("INSERT INTO schema_migrations(version) VALUES (%s)", (version,))
                raw.commit()
                applied_now.append(version)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
            conn.commit()
    return applied_now


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Applied:", run_migrations() or "nothing (up to date)")
