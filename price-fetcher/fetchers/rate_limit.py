"""
Lambda-aware rate limiting configuration.

Provides reduced sleep times and retry limits for Lambda execution
to maximize throughput within the 15-minute timeout constraint.

Supports per-service configuration via environment variables:
    FMP_TIER=starter|premium|ultimate (default: free)
    TWELVEDATA_TIER=grow|pro|enterprise (default: free)
    FINNHUB_TIER=paid (default: free)
    ALPHA_VANTAGE_TIER=paid_30|paid_75|paid_150|paid_300 (default: free)
"""

import os
import time
from typing import Optional

from logging_config import get_logger

logger = get_logger(__name__)


# Service-specific tier configurations
# Each service has different rate limits based on subscription tier
#
# Paid tiers use min_delay=0 (burst mode) since:
# - Most APIs measure rate limits per minute, not requiring even spacing
# - Lambda runs infrequently (e.g., every 5 min), so bursting is safe
# - Reduces Lambda execution time and cost
# - 429 handling provides safety net if limits are exceeded
SERVICE_TIERS = {
    'fmp': {
        'free': {'per_minute': None, 'per_day': 250, 'min_delay': 2.0},
        'starter': {'per_minute': 300, 'per_day': None, 'min_delay': 0.0},   # Burst mode
        'premium': {'per_minute': 750, 'per_day': None, 'min_delay': 0.0},   # Burst mode
        'ultimate': {'per_minute': 3000, 'per_day': None, 'min_delay': 0.0}, # Burst mode
    },
    'twelvedata': {
        'free': {'per_minute': 8, 'per_day': 800, 'min_delay': 8.0},
        'grow': {'per_minute': 800, 'per_day': None, 'min_delay': 0.0},       # Burst mode
        'pro': {'per_minute': 4000, 'per_day': None, 'min_delay': 0.0},       # Burst mode
        'enterprise': {'per_minute': 12000, 'per_day': None, 'min_delay': 0.0}, # Burst mode
    },
    'finnhub': {
        'free': {'per_minute': 60, 'per_day': None, 'min_delay': 1.0},
        'paid': {'per_minute': 300, 'per_day': None, 'min_delay': 0.0},       # Burst mode
    },
    'alphavantage': {
        'free': {'per_minute': 5, 'per_day': 25, 'min_delay': 2.0},
        'paid_30': {'per_minute': 30, 'per_day': None, 'min_delay': 0.0},     # Burst mode
        'paid_75': {'per_minute': 75, 'per_day': None, 'min_delay': 0.0},     # Burst mode
        'paid_150': {'per_minute': 150, 'per_day': None, 'min_delay': 0.0},   # Burst mode
        'paid_300': {'per_minute': 300, 'per_day': None, 'min_delay': 0.0},   # Burst mode
    },
}


def is_lambda_environment() -> bool:
    """Check if running in Lambda environment."""
    return bool(os.getenv('AWS_LAMBDA_FUNCTION_NAME'))


def get_service_tier(service: str) -> str:
    """
    Get the configured tier for a service from environment variables.

    Environment variables:
        FMP_TIER, TWELVEDATA_TIER, FINNHUB_TIER, ALPHA_VANTAGE_TIER

    Returns:
        Tier name (lowercase), defaults to 'free'
    """
    env_var_map = {
        'fmp': 'FMP_TIER',
        'twelvedata': 'TWELVEDATA_TIER',
        'finnhub': 'FINNHUB_TIER',
        'alphavantage': 'ALPHA_VANTAGE_TIER',
    }
    env_var = env_var_map.get(service.lower())
    if env_var:
        return os.getenv(env_var, 'free').lower()
    return 'free'


def get_service_rate_config(service: str) -> dict:
    """
    Get rate limiting configuration for a specific API service.

    Uses the service's configured tier (via environment variable) to determine
    appropriate rate limits. Combines with Lambda-aware retry/backoff settings.

    Args:
        service: Service name ('fmp', 'twelvedata', 'finnhub', 'alphavantage')

    Returns:
        Dict with rate limiting parameters:
        - per_minute: Requests per minute limit (or None if unlimited)
        - per_day: Requests per day limit (or None if unlimited)
        - min_delay: Minimum seconds between requests
        - max_retries: Maximum retry attempts
        - base_backoff: Initial backoff seconds
        - max_backoff: Maximum backoff seconds
        - tier: The tier being used
    """
    service = service.lower()
    tier = get_service_tier(service)

    # Get service-specific limits
    service_tiers = SERVICE_TIERS.get(service, {})
    tier_config = service_tiers.get(tier, service_tiers.get('free', {}))

    # Merge with Lambda/local retry settings
    base_config = get_rate_limit_config()

    config = {
        'per_minute': tier_config.get('per_minute'),
        'per_day': tier_config.get('per_day'),
        'min_delay': tier_config.get('min_delay', 1.0),
        'max_retries': base_config['max_retries'],
        'base_backoff': base_config['base_backoff'],
        'max_backoff': base_config['max_backoff'],
        'tier': tier,
        'service': service,
    }

    logger.debug(
        "Service rate config",
        extra={'service': service, 'tier': tier, 'config': config}
    )

    return config


def get_rate_limit_config() -> dict:
    """
    Get rate limiting configuration, optimized for Lambda when applicable.

    Lambda uses shorter delays and fewer retries to maximize symbols
    processed within timeout constraints.

    Returns:
        Dict with rate limiting parameters:
        - request_delay: Minimum seconds between requests
        - max_retries: Maximum retry attempts
        - base_backoff: Initial backoff seconds
        - max_backoff: Maximum backoff seconds
    """
    is_lambda = is_lambda_environment()

    if is_lambda:
        # Lambda: shorter delays, fewer retries
        return {
            'request_delay': float(os.getenv('LAMBDA_REQUEST_DELAY', '0.5')),
            'max_retries': int(os.getenv('LAMBDA_MAX_RETRIES', '2')),
            'base_backoff': int(os.getenv('LAMBDA_BASE_BACKOFF', '5')),
            'max_backoff': int(os.getenv('LAMBDA_MAX_BACKOFF', '30')),
        }
    else:
        # Local: standard delays
        return {
            'request_delay': float(os.getenv('REQUEST_DELAY', '1.0')),
            'max_retries': int(os.getenv('MAX_RETRIES', '5')),
            'base_backoff': int(os.getenv('BASE_BACKOFF', '10')),
            'max_backoff': int(os.getenv('MAX_BACKOFF', '160')),
        }


def calculate_backoff(attempt: int, config: Optional[dict] = None) -> float:
    """
    Calculate exponential backoff time, capped for Lambda.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Rate limit config (uses get_rate_limit_config if None)

    Returns:
        Backoff time in seconds
    """
    if config is None:
        config = get_rate_limit_config()

    backoff = min(
        config['base_backoff'] * (2 ** attempt),
        config['max_backoff']
    )

    return float(backoff)


def rate_limited_sleep(
    attempt: int,
    config: Optional[dict] = None,
    reason: str = ""
) -> None:
    """
    Sleep with exponential backoff, capped for Lambda.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Rate limit config (uses get_rate_limit_config if None)
        reason: Reason for sleep (for logging)
    """
    if config is None:
        config = get_rate_limit_config()

    sleep_time = calculate_backoff(attempt, config)

    logger.debug(
        "Rate limit backoff",
        extra={
            'sleep_seconds': sleep_time,
            'attempt': attempt,
            'reason': reason,
            'is_lambda': is_lambda_environment()
        }
    )

    time.sleep(sleep_time)


def should_retry(attempt: int, config: Optional[dict] = None) -> bool:
    """
    Check if another retry attempt should be made.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Rate limit config (uses get_rate_limit_config if None)

    Returns:
        True if more retries allowed
    """
    if config is None:
        config = get_rate_limit_config()

    return attempt < config['max_retries']
