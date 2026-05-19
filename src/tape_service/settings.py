from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(...)
    db_pool_min_size: int = 1
    db_pool_max_size: int = 10

    redis_url: str = Field(...)
    redis_max_connections: int = 20

    session_secret: str = Field(..., min_length=32)
    session_cookie_name: str = "s3p_session"
    session_cookie_secure: bool = True
    session_cookie_samesite: str = "lax"
    session_absolute_ttl_days: int = 30
    session_idle_ttl_days: int = 14

    login_rate_limit_per_ip: int = 10
    login_rate_limit_window_seconds: int = 300

    worker_interval_seconds: int = 60
    worker_advisory_lock_ttl_seconds: int = 600

    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _check_database_url(cls, v: str) -> str:
        if not v.startswith(("postgres://", "postgresql://")):
            raise ValueError("database_url must be a postgresql:// connection string")
        return v

    @field_validator("redis_url")
    @classmethod
    def _check_redis_url(cls, v: str) -> str:
        if not v.startswith(("redis://", "rediss://", "unix://")):
            raise ValueError("redis_url must be a redis://, rediss://, or unix:// connection string")
        return v

    @field_validator("session_cookie_samesite")
    @classmethod
    def _samesite_lower(cls, v: str) -> str:
        v = v.lower()
        if v not in {"lax", "strict", "none"}:
            raise ValueError("samesite must be one of lax|strict|none")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
