from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ERP_", extra="ignore")

    app_name: str = "智能物资管理系统"
    env: str = "dev"
    debug: bool = True

    database_url: str = "postgresql+psycopg://erp:erp@127.0.0.1:5433/erp"

    jwt_secret: str = "dev-only-secret-please-change-me-32bytes"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    cors_origins: str = "http://localhost:5173"

    admin_username: str = "admin"
    admin_password: str = "admin123"

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
