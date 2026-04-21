"""
Configuracion de la aplicacion - v2.0
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # General
    APP_NAME: str = "SQA Kinetix Pro"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database — set via DATABASE_URL env var
    DATABASE_URL: str = "postgresql://jmeter_user:jmeter_secure_2024@postgres:5432/jmeter_analyzer_db"

    # Security — MUST override SECRET_KEY in production
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Admin seed password — override via ADMIN_DEFAULT_PASSWORD env var
    ADMIN_DEFAULT_PASSWORD: str = "sqa2024"

    # Backend
    BACKEND_PORT: int = 8001
    BACKEND_HOST: str = "0.0.0.0"

    # Gemini AI — set via GEMINI_API_KEY env var
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # File Upload
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE_MB: int = 100

    # CORS (comma-separated origins)
    CORS_ORIGINS: str = ""
    CORS_ORIGINS_DEV: str = "http://localhost:5173,http://localhost:3000"

    # Cookie security — True in production (HTTPS only)
    COOKIE_SECURE: bool = False

    # Fernet encryption key for sensitive data (monitoring tokens)
    # Override via FERNET_KEY env var in production
    FERNET_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
