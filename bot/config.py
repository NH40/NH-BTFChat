"""Настройки из .env (pydantic-settings)."""
from __future__ import annotations

from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "db"
    postgres_port: int = 5432

    redis_url: str = "redis://redis:6379/0"

    # Владельцы (полный доступ к боту и Mini App), через запятую: OWNER_IDS=123,456.
    owner_ids_raw: str = Field(default="", alias="OWNER_IDS")
    # Часовой пояс команды — в нём вводятся и показываются сроки и время напоминаний.
    timezone: str = "Europe/Moscow"
    # Публичный адрес Mini App (кнопка «Открыть» в боте). Пусто — кнопка не показывается.
    mini_app_url: str = ""

    db_pool_size: int = 5

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def owner_ids(self) -> set[int]:
        return {int(x) for x in self.owner_ids_raw.replace(" ", "").split(",") if x}

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
