from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://aiteacher:aiteacher@localhost:5433/aiteacher"
    test_database_url: str = "postgresql+psycopg://aiteacher:aiteacher@localhost:5433/aiteacher_test"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 12

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AITEACHER_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
