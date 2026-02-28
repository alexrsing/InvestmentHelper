import json
import boto3
from pydantic_settings import BaseSettings
from typing import List


def _load_secrets(secret_name: str = "investment-helper/config", region: str = "us-east-1") -> dict:
    """Fetch sensitive config from AWS Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])


_secrets = _load_secrets()


class Settings(BaseSettings):
    """Application settings and configuration"""

    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Investment Helper API"

    # Clerk Auth (from AWS Secrets Manager)
    CLERK_SECRET_KEY: str = _secrets["CLERK_SECRET_KEY"]
    CLERK_JWKS_URL: str = _secrets["CLERK_JWKS_URL"]
    CLERK_ISSUER: str = _secrets["CLERK_ISSUER"]
    CLERK_AUDIENCE: str | None = _secrets.get("CLERK_AUDIENCE")

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # AWS Settings
    AWS_REGION: str = "us-east-1"

    # Database
    DYNAMODB_ENDPOINT: str | None = None  # For local development

    # Research
    RESEARCH_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = _secrets.get("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-2.0-flash"
    RESEARCH_EXPIRY_HOURS: int = 24

    class Config:
        case_sensitive = True


settings = Settings()
