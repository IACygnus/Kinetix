"""
Configuración de la aplicación
"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # General
    APP_NAME: str = "JMeter Analyzer Pro"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "postgresql://jmeter_user:jmeter_secure_2024@postgres:5432/jmeter_analyzer_db"
    
    # Security
    SECRET_KEY: str = "bKp_8xN9mQ2vR5wZ1aE7fH3jL6kM0nY4cT2sW8dX1gV5pU9iO3hB7eN0qA4rJ6m"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Backend
    BACKEND_PORT: int = 8001
    BACKEND_HOST: str = "0.0.0.0"
    
    # Gemini AI - MODELO CORREGIDO
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-pro"  # CAMBIADO DE gemini-1.5-pro
    
    # File Upload
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE_MB: int = 100
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# CORS Origins hardcoded
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000"
]