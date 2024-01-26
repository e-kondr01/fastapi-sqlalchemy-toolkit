from pathlib import Path

from pydantic import FieldValidationInfo, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve(strict=True).parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env", case_sensitive=True, extra="allow"
    )
    # PostgreSQL Database Connection
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    SQLALCHEMY_DATABASE_URL: str | None = None

    @field_validator("SQLALCHEMY_DATABASE_URL", mode="before")
    def assemble_db_connection_string(
        cls, value: PostgresDsn | None, info: FieldValidationInfo
    ) -> str | PostgresDsn:
        if isinstance(value, str):
            return value
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=info.data["POSTGRES_USER"],
                password=info.data["POSTGRES_PASSWORD"],
                host=info.data["POSTGRES_HOST"],
                port=info.data["POSTGRES_PORT"],
                path=info.data["POSTGRES_DB"],
            )
        )


settings = Settings()
