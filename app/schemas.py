from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"

    rate_limit_limit: int = 100
    rate_limit_window_seconds: int = 60

    redis_timeout_seconds: float = 0.25
    redis_max_connections: int = 128

    # If True, requests are allowed when Redis is unavailable.
    # If False, requests are denied / middleware returns 503.
    rate_limit_fail_open: bool = True

    protected_path_prefixes: tuple[str, ...] = ("/demo", "/private")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()