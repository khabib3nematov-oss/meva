from functools import lru_cache
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    bot_token: SecretStr | None = None
    boss_channel_id: str | int | None = Field(default=None, alias="BOSS_CHANNEL_ID")
    owner_telegram_ids: str = "1002484373,5867823541"

    timezone: str = "Asia/Tashkent"
    log_level: str = "INFO"

    database_url: str | None = None
    use_sqlite: bool = False
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "mevachi"
    postgres_password: SecretStr = Field(default_factory=lambda: SecretStr(""))
    postgres_db: str = "mevachi"

    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    @field_validator("database_url", mode="before")
    @classmethod
    def empty_database_url_to_none(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {value}") from exc
        return value

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def required_bot_token(self) -> str:
        if self.bot_token is None:
            raise RuntimeError("BOT_TOKEN is required to start the Telegram bot.")

        token = self.bot_token.get_secret_value().strip()
        if not token:
            raise RuntimeError("BOT_TOKEN is required to start the Telegram bot.")

        return token

    @property
    def owner_ids(self) -> frozenset[int]:
        return frozenset(
            int(value.strip())
            for value in self.owner_telegram_ids.split(",")
            if value.strip()
        )

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.use_sqlite:
            return "sqlite+aiosqlite:///./mevachi.db"

        if self.database_url:
            if self.database_url.startswith("postgresql://"):
                return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            if self.database_url.startswith("postgres://"):
                return self.database_url.replace("postgres://", "postgresql+asyncpg://", 1)
            return self.database_url

        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password.get_secret_value())
        database = quote_plus(self.postgres_db)
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{database}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
