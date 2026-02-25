"""
Secure logging utilities for credential masking.

Prevents accidental exposure of API keys and sensitive data in CloudWatch logs.

Usage:
    from pricedata.secure_logging import mask_api_key, get_logger

    logger = get_logger(__name__)
    logger.info(f"Using API key: {mask_api_key(api_key)}")
"""

import logging
import os
from typing import Any, Optional


def mask_api_key(api_key: Optional[str], visible_chars: int = 4) -> str:
    """Mask API key showing only first N characters.

    Args:
        api_key: The API key to mask
        visible_chars: Number of characters to show (default: 4)

    Returns:
        Masked string like "abc1********"

    Examples:
        >>> mask_api_key("abc123xyz789")
        'abc1********'
        >>> mask_api_key("short")
        '****'
        >>> mask_api_key(None)
        '****'
    """
    if not api_key or len(api_key) <= visible_chars:
        return "****"
    return api_key[:visible_chars] + "*" * 8


def mask_secret_name(secret_name: Optional[str]) -> str:
    """Mask secret name for logging, showing only environment and key name.

    Args:
        secret_name: Full secret path like "dev/price-fetcher/alpha-vantage-api-key"

    Returns:
        Shortened path like "dev/.../alpha-vantage-api-key"

    Examples:
        >>> mask_secret_name("dev/price-fetcher/alpha-vantage-api-key")
        'dev/.../alpha-vantage-api-key'
        >>> mask_secret_name("simple-secret")
        'simple-secret'
        >>> mask_secret_name(None)
        '****'
    """
    if not secret_name:
        return "****"
    parts = secret_name.split("/")
    if len(parts) >= 3:
        return f"{parts[0]}/.../{parts[-1]}"
    return secret_name


def safe_log_config(config: dict) -> dict:
    """Return config dict with sensitive values masked.

    Automatically detects and masks values for keys containing:
    'key', 'secret', 'password', 'token', 'credential', 'auth'

    Args:
        config: Configuration dictionary

    Returns:
        New dictionary with sensitive values masked

    Examples:
        >>> safe_log_config({"api_key": "secret123", "region": "us-west-2"})
        {'api_key': 'secr********', 'region': 'us-west-2'}
    """
    sensitive_patterns = ["key", "secret", "password", "token", "credential", "auth"]
    masked = {}
    for k, v in config.items():
        if any(pattern in k.lower() for pattern in sensitive_patterns):
            masked[k] = mask_api_key(str(v)) if v else None
        else:
            masked[k] = v
    return masked


def get_logger(name: str) -> logging.Logger:
    """Get a logger configured for Lambda/CloudWatch compatibility.

    In Lambda environment, uses JSON-friendly format.
    Locally, uses human-readable format.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already done (avoid duplicate handlers)
    if not logger.handlers:
        handler = logging.StreamHandler()

        # Use different format based on environment
        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            # Lambda: simpler format (CloudWatch adds timestamp)
            formatter = logging.Formatter(
                "%(levelname)s - %(name)s - %(message)s"
            )
        else:
            # Local: include timestamp
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
            )

        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger


def log_api_call(
    logger: logging.Logger,
    api_name: str,
    endpoint: str,
    success: bool,
    duration_ms: Optional[float] = None,
    error: Optional[Exception] = None,
) -> None:
    """Safely log API call without exposing credentials.

    Args:
        logger: Logger instance
        api_name: Name of the API (e.g., "AlphaVantage")
        endpoint: API endpoint or function called
        success: Whether the call succeeded
        duration_ms: Optional duration in milliseconds
        error: Optional exception (only type is logged, not message)
    """
    status = "SUCCESS" if success else "FAILED"
    msg = f"API Call: {api_name} -> {endpoint} [{status}]"

    if duration_ms is not None:
        msg += f" ({duration_ms:.0f}ms)"

    if error:
        # Only log error type, not message (which might contain credentials)
        msg += f" Error: {type(error).__name__}"

    if success:
        logger.info(msg)
    else:
        logger.warning(msg)


def redact_url(url: Optional[str]) -> str:
    """Redact API keys from URLs.

    Args:
        url: URL that may contain API key parameters

    Returns:
        URL with api key values replaced with [REDACTED]

    Examples:
        >>> redact_url("https://api.example.com?apikey=secret123&symbol=AAPL")
        'https://api.example.com?apikey=[REDACTED]&symbol=AAPL'
    """
    if not url:
        return "****"

    import re

    # Common API key parameter patterns
    patterns = [
        (r"(apikey=)[^&]+", r"\1[REDACTED]"),
        (r"(api_key=)[^&]+", r"\1[REDACTED]"),
        (r"(token=)[^&]+", r"\1[REDACTED]"),
        (r"(key=)[^&]+", r"\1[REDACTED]"),
        (r"(access_token=)[^&]+", r"\1[REDACTED]"),
    ]

    result = url
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result
