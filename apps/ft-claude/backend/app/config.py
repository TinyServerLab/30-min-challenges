from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_minutes: int = 30
    jwt_refresh_days: int = 7
    cors_origins: str = ""
    # URL prefix the app is served under behind a path-routing proxy, e.g.
    # "/finance" for https://apps.tinyserverlab.in/finance. Empty = site root.
    base_path: str = ""

    @field_validator("base_path")
    @classmethod
    def _normalize_base_path(cls, v: str) -> str:
        v = v.strip().strip("/")
        return f"/{v}" if v else ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
