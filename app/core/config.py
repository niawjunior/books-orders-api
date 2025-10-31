from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import ClassVar

class Settings(BaseSettings):
    PROJECT_NAME: str = "Books Orders API"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/books_orders_db"
    )

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow",
    )

@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
