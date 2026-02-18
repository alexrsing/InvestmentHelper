from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings and configuration"""

    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Investment Helper API"

    # Security
    SECRET_KEY: str  # Required - must be set in .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # AWS Settings
    AWS_REGION: str = "us-east-1"

    # Database
    DYNAMODB_ENDPOINT: str | None = None  # For local development

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
