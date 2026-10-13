from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://finance:finance@db:5432/finance"
    jwt_secret: str = "change-me-in-.env"
    jwt_expiry_days: int = 7
    # a fresh cookie is issued when the current one is older than this (sliding session)
    jwt_refresh_after_hours: int = 12
    cookie_secure: bool = True  # true behind Cloudflare (HTTPS); false for plain LAN testing
    currency_symbol: str = "₹"
    app_name: str = "Household Ledger"

    # seeded on first start if no users exist
    admin_email: str = ""
    admin_password: str = ""
    admin_name: str = "Admin"


settings = Settings()
