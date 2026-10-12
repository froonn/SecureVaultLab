from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "dev"
    app_secret_key: str = "change_me"

    database_url: str = "sqlite:////data/app.db"

    session_ttl_minutes: int = 60
    cookie_secure: bool = True
    cookie_samesite: str = "lax"
    cookie_name: str = "sid"
    csrf_cookie_name: str = "csrf_token"
    csrf_header_name: str = "X-CSRF-Token"

    fernet_key_file: str = "/run/secrets/fernet_key"

    log_level: str = "INFO"

    @property
    def is_dev(self) -> bool:
        return self.app_env.lower() in {"dev", "development", "local"}

    @property
    def fernet_key(self) -> bytes:
        return Path(self.fernet_key_file).read_bytes().strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()