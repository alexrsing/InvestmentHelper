"""
API key loader with single JSON secret from AWS Secrets Manager.

In Lambda: loads all keys/tiers from one Secrets Manager JSON secret.
Locally: falls back to environment variables (for .env-based development).
"""

import json
import os
from typing import Optional

from logging_config import get_logger

logger = get_logger(__name__)

# Module-level cache: None = not loaded yet, {} = loaded (possibly empty)
_secrets_cache: Optional[dict] = None


def _load_secrets() -> dict:
    """Load the JSON secret from AWS Secrets Manager.

    Reads the secret name from PRICE_FETCHER_SECRET_NAME env var
    (default: 'price-fetcher/config'), fetches from Secrets Manager,
    and parses the JSON. Returns {} on any failure.
    """
    secret_name = os.getenv("PRICE_FETCHER_SECRET_NAME", "price-fetcher/config")
    region = os.getenv("AWS_REGION", os.getenv("AWS_REGION_NAME", "us-east-1"))

    try:
        import boto3
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        secrets = json.loads(response["SecretString"])
        logger.info("Loaded secrets from Secrets Manager: %s", secret_name)
        return secrets
    except Exception as e:
        logger.warning(
            "Could not load secrets from Secrets Manager (%s): %s",
            secret_name, type(e).__name__
        )
        return {}


def _get_secrets() -> dict:
    """Get cached secrets dict.

    In Lambda (AWS_LAMBDA_FUNCTION_NAME set): loads from Secrets Manager
    on first call, caches for container reuse.
    Locally: returns {} so get_api_key() falls through to os.getenv().
    """
    global _secrets_cache

    if _secrets_cache is not None:
        return _secrets_cache

    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        _secrets_cache = _load_secrets()
    else:
        _secrets_cache = {}

    return _secrets_cache


def get_api_key(key_name: str) -> Optional[str]:
    """
    Get an API key or config value by name.

    Tries the JSON secret first (in Lambda), then falls back to
    os.getenv(). Rejects placeholder values starting with 'your_'.

    Args:
        key_name: The key name (e.g., 'ALPHA_VANTAGE_API_KEY', 'FMP_TIER')

    Returns:
        The value, or None if not found/configured.
    """
    # Try secrets cache first
    value = _get_secrets().get(key_name)

    # Fall back to environment variable
    if not value:
        value = os.getenv(key_name)

    # Reject placeholder values
    if value and value.startswith("your_"):
        logger.warning(
            "%s appears to be a placeholder value, treating as not configured",
            key_name
        )
        return None

    return value


def is_api_key_configured(key_name: str) -> bool:
    """
    Check if an API key is configured.

    Args:
        key_name: The key name (e.g., 'ALPHA_VANTAGE_API_KEY')

    Returns:
        True if the key is available, False otherwise.
    """
    return get_api_key(key_name) is not None


def clear_cache() -> None:
    """Reset the secrets cache. Useful for testing."""
    global _secrets_cache
    _secrets_cache = None
