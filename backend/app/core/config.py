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

    # 附件（§13.3）：文件本体落本地磁盘，DB 只存元数据与相对路径
    attachment_dir: str = "data/attachments"
    attachment_max_size_mb: int = 10
    attachment_allowed_ext: str = (
        ".png,.jpg,.jpeg,.gif,.webp,.bmp,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.json,.xml,.zip"
    )
    attachment_allowed_types: str = (
        "image/,application/pdf,text/,application/json,application/xml,application/zip,"
        "application/msword,application/vnd.openxmlformats-officedocument,"
        "application/vnd.ms-excel,application/vnd.ms-powerpoint"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def attachment_allowed_ext_set(self) -> set[str]:
        return {x.strip().lower() for x in self.attachment_allowed_ext.split(",") if x.strip()}

    @property
    def attachment_allowed_type_prefixes(self) -> tuple[str, ...]:
        return tuple(x.strip().lower() for x in self.attachment_allowed_types.split(",") if x.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
