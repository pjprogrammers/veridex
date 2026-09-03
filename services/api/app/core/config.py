"""VERIDEX API - Core Configuration"""
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "veridex"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # Database override (defaults to PostgreSQL; set DATABASE_URL to run
    # standalone, e.g. "sqlite+aiosqlite:///./veridex.db" for local dev/demo)
    DATABASE_URL: str | None = None

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "veridex"
    POSTGRES_USER: str = "veridex"
    POSTGRES_PASSWORD: str = "veridex_dev_password"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # MinIO/S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "veridex_minio"
    MINIO_SECRET_KEY: str = "veridex_minio_secret"
    MINIO_BUCKET: str = "veridex-documents"
    MINIO_USE_SSL: bool = False

    # JWT
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 20
    ALLOWED_MIME_TYPES: str = "image/jpeg,image/png,image/tiff,application/pdf"

    # OCR
    OCR_ENGINE: str = "paddleocr"

    # Face Verification
    FACE_MODEL_NAME: str = "arcface_r100_v1"
    FACE_SIMILARITY_THRESHOLD: float = 0.4
    FACE_ENGINE: str = "baseline"

    # Risk Scoring
    RISK_HIGH_THRESHOLD: float = 0.7
    RISK_MEDIUM_THRESHOLD: float = 0.4

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def allowed_mime_types(self) -> list[str]:
        return [t.strip() for t in self.ALLOWED_MIME_TYPES.split(",")]

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
