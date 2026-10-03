from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- database (shared PostgreSQL, dedicated database) ---
    db_host: str = "shared-postgres"
    db_port: int = 5432
    db_name: str = "home_inventory"
    db_user: str = "home_inventory_user"
    db_password: str = ""
    db_sslmode: str = "prefer"
    db_pool_size: int = 5

    # --- hosting ---
    base_path: str = "/inventory"            # app is served under this prefix
    public_url: str = "https://home.tinyserverlab.in/inventory"  # used in reminder links
    enable_api_docs: bool = False

    # --- auth ---
    cookie_name: str = "hi_session"
    cookie_secure: bool = True               # set false only for plain-http local testing
    session_days: int = 30
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15

    # bootstrap admin (only used when the users table is empty)
    admin_email: str | None = None
    admin_password: str | None = None
    admin_name: str = "Admin"

    # --- files ---
    upload_dir: Path = Path("/data/uploads")
    max_upload_mb: int = 20
    enable_ocr: bool = True
    ocr_lang: str = "eng"

    # --- reminders ---
    tz: str = "Asia/Kolkata"
    reminder_days: str = "30,7,0"            # days before expiry
    reminder_hour: int = 9
    reminder_minute: int = 0
    expiring_soon_days: int = 30             # dashboard "expiring soon" window
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    ntfy_url: str | None = None              # e.g. https://ntfy.sh/my-home-warranty
    ntfy_token: str | None = None
    # Discord and Telegram are configured in Settings → Notifications (stored in the DB).
    telegram_api_base: str = "https://api.telegram.org"   # change only for a self-hosted Bot API server

    default_currency: str = "INR"

    @field_validator("base_path")
    @classmethod
    def _norm_base(cls, v: str) -> str:
        v = (v or "").strip().rstrip("/")
        if v and not v.startswith("/"):
            v = "/" + v
        return v

    @property
    def reminder_day_list(self) -> list[int]:
        return sorted({int(x) for x in self.reminder_days.split(",") if x.strip()}, reverse=True)

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus
        return (f"postgresql+psycopg://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}?sslmode={self.db_sslmode}")

    @property
    def cookie_path(self) -> str:
        return self.base_path or "/"


@lru_cache
def get_settings() -> Settings:
    return Settings()
