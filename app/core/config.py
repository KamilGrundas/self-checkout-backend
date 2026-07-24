import secrets
import warnings
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AnyHttpUrl,
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    BACKEND_PUBLIC_URL: AnyHttpUrl | None = None
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    DATABASE_URL: PostgresDsn | None = None
    DB_CONNECT_TIMEOUT: int = 10
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    S3_ENDPOINT_URL: AnyHttpUrl | None = None
    S3_REGION: str = "us-east-1"
    S3_BUCKET: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_SESSION_TOKEN: str | None = None
    S3_USE_SSL: bool = False
    S3_FORCE_PATH_STYLE: bool = True
    S3_VERIFY_TLS: bool = True
    S3_CONNECT_TIMEOUT: int = 5
    S3_READ_TIMEOUT: int = 30
    S3_MAX_RETRIES: int = 3
    S3_CREATE_BUCKETS: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        if self.DATABASE_URL is None:
            raise ValueError("DATABASE_URL is required")
        return self.DATABASE_URL

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self

    @model_validator(mode="after")
    def _validate_external_services(self) -> Self:
        is_local = self.ENVIRONMENT == "local"
        if self.DATABASE_URL is None:
            if not is_local:
                raise ValueError("DATABASE_URL is required outside local development")
            self.DATABASE_URL = PostgresDsn(
                "postgresql+psycopg://postgres:postgres@localhost:5432/app"
            )
        if self.BACKEND_PUBLIC_URL is None:
            if not is_local:
                raise ValueError(
                    "BACKEND_PUBLIC_URL is required outside local development"
                )
            self.BACKEND_PUBLIC_URL = AnyHttpUrl("http://localhost:8000")

        if self.S3_ENDPOINT_URL is None:
            if not is_local:
                raise ValueError(
                    "S3_ENDPOINT_URL is required outside local development"
                )
            self.S3_ENDPOINT_URL = AnyHttpUrl("http://localhost:8082")
        if self.S3_BUCKET is None:
            if not is_local:
                raise ValueError("S3_BUCKET is required outside local development")
            self.S3_BUCKET = "product-images"
        if bool(self.S3_ACCESS_KEY_ID) != bool(self.S3_SECRET_ACCESS_KEY):
            raise ValueError(
                "S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY must be set together"
            )
        if self.S3_SESSION_TOKEN and not self.S3_ACCESS_KEY_ID:
            raise ValueError("S3_SESSION_TOKEN requires S3 access credentials")
        if self.S3_CREATE_BUCKETS and not is_local:
            raise ValueError("S3_CREATE_BUCKETS is allowed only in local development")
        if self.S3_ENDPOINT_URL.scheme == "https" and not self.S3_USE_SSL:
            raise ValueError("S3_USE_SSL must be true for an https S3_ENDPOINT_URL")
        if self.S3_ENDPOINT_URL.scheme == "http" and self.S3_USE_SSL:
            raise ValueError("S3_USE_SSL must be false for an http S3_ENDPOINT_URL")
        return self


settings = Settings()  # type: ignore
