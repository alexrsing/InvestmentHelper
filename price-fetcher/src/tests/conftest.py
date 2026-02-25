"""
Shared pytest fixtures for price-fetcher tests.

Provides mocked AWS services (DynamoDB, Secrets Manager) and
common test utilities.
"""

import json
import os
import sys
from decimal import Decimal
from datetime import date, datetime, timezone
from typing import Dict, Any, Generator
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

# Add fetchers to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'fetchers'))


# =============================================================================
# Environment Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def reset_environment(monkeypatch):
    """Reset environment variables and singletons between tests."""
    # Clear any existing API key env vars
    for key in [
        'ALPHA_VANTAGE_API_KEY', 'ALPHA_VANTAGE_TIER',
        'TWELVEDATA_API_KEY', 'TWELVEDATA_TIER',
        'FINNHUB_API_KEY', 'FINNHUB_TIER',
        'FMP_API_KEY', 'FMP_TIER',
        'PRICE_FETCHER_SECRET_NAME',
        'AWS_LAMBDA_FUNCTION_NAME', 'DATA_SOURCE',
        'ENVIRONMENT', 'AWS_REGION',
    ]:
        monkeypatch.delenv(key, raising=False)

    # Set default region
    monkeypatch.setenv('AWS_REGION', 'us-west-2')
    monkeypatch.setenv('ENVIRONMENT', 'test')

    yield

    # Reset singletons after test
    _reset_singletons()


def _reset_singletons():
    """Reset module-level singletons to ensure test isolation."""
    try:
        import api_keys
        api_keys.clear_cache()
    except (ImportError, AttributeError):
        pass


# =============================================================================
# AWS Mock Fixtures
# =============================================================================

@pytest.fixture
def aws_credentials(monkeypatch):
    """Mock AWS credentials for moto."""
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'testing')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'testing')
    monkeypatch.setenv('AWS_SECURITY_TOKEN', 'testing')
    monkeypatch.setenv('AWS_SESSION_TOKEN', 'testing')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-west-2')


@pytest.fixture
def mock_secretsmanager(aws_credentials):
    """Create a mocked Secrets Manager with test API keys (single JSON secret)."""
    with mock_aws():
        client = boto3.client('secretsmanager', region_name='us-west-2')

        # Create single JSON secret with all keys and tiers
        config_secret = {
            "ALPHA_VANTAGE_API_KEY": "test-av-key-12345",
            "ALPHA_VANTAGE_TIER": "free",
            "TWELVEDATA_API_KEY": "test-td-key-12345",
            "TWELVEDATA_TIER": "free",
            "FINNHUB_API_KEY": "test-fh-key-12345",
            "FINNHUB_TIER": "free",
            "FMP_API_KEY": "test-fmp-key-12345",
            "FMP_TIER": "free",
        }

        client.create_secret(
            Name='test/price-fetcher/config',
            SecretString=json.dumps(config_secret)
        )

        yield client


@pytest.fixture
def mock_dynamodb(aws_credentials, monkeypatch):
    """Create mocked DynamoDB tables for testing.

    Creates both legacy table names and new marketdata-{env}-{table} names
    to support testing during migration.
    """
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

        # New marketdata-{env}-{table} convention
        # Set environment variables to use new table names
        monkeypatch.setenv('PRICES_TABLE', 'marketdata-test-prices')
        monkeypatch.setenv('CONFIG_TABLE_NAME', 'marketdata-test-config')
        monkeypatch.setenv('WATCHLIST_TABLE', 'marketdata-test-watchlist')

        # Create new marketdata-test-prices table
        prices_table = dynamodb.create_table(
            TableName='marketdata-test-prices',
            KeySchema=[
                {'AttributeName': 'etf_symbol', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'etf_symbol', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # Create watchlist table (replaces legacy positions table)
        watchlist_table = dynamodb.create_table(
            TableName='marketdata-test-watchlist',
            KeySchema=[
                {'AttributeName': 'symbol', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'symbol', 'AttributeType': 'S'},
                {'AttributeName': 'symbol_type', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'symbol_type-index',
                    'KeySchema': [{'AttributeName': 'symbol_type', 'KeyType': 'HASH'}],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # Create new marketdata-test-config table
        config_table = dynamodb.create_table(
            TableName='marketdata-test-config',
            KeySchema=[
                {'AttributeName': 'config_type', 'KeyType': 'HASH'},
                {'AttributeName': 'config_key', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'config_type', 'AttributeType': 'S'},
                {'AttributeName': 'config_key', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # Wait for tables to be created
        prices_table.meta.client.get_waiter('table_exists').wait(
            TableName='marketdata-test-prices'
        )
        watchlist_table.meta.client.get_waiter('table_exists').wait(
            TableName='marketdata-test-watchlist'
        )
        config_table.meta.client.get_waiter('table_exists').wait(
            TableName='marketdata-test-config'
        )

        yield {
            'dynamodb': dynamodb,
            'watchlist_table': watchlist_table,
            'prices_table': prices_table,
            'config_table': config_table,
        }


@pytest.fixture
def seeded_watchlist(mock_dynamodb):
    """Seed watchlist table with test symbols."""
    from tests.integration.helpers import add_watchlist_symbol
    table = mock_dynamodb['watchlist_table']

    symbols = ['SPY', 'QQQ', 'IWM', 'DIA', 'VTI']
    for symbol in symbols:
        add_watchlist_symbol(table, symbol)

    return symbols


# =============================================================================
# Lambda Context Fixture
# =============================================================================

class MockLambdaContext:
    """Mock AWS Lambda context object."""

    def __init__(self, remaining_time_ms: int = 300000):
        self._remaining_time_ms = remaining_time_ms
        self.function_name = 'test-price-fetcher'
        self.function_version = '$LATEST'
        self.invoked_function_arn = 'arn:aws:lambda:us-west-2:123456789:function:test-price-fetcher'
        self.memory_limit_in_mb = 512
        self.aws_request_id = 'test-request-id'
        self.log_group_name = '/aws/lambda/test-price-fetcher'
        self.log_stream_name = 'test-log-stream'

    def get_remaining_time_in_millis(self) -> int:
        return self._remaining_time_ms


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context with 5 minutes remaining."""
    return MockLambdaContext(remaining_time_ms=300000)


@pytest.fixture
def lambda_context_low_time():
    """Create a mock Lambda context with only 30 seconds remaining."""
    return MockLambdaContext(remaining_time_ms=30000)


# =============================================================================
# API Response Fixtures
# =============================================================================

@pytest.fixture
def sample_quote_response() -> Dict[str, Any]:
    """Sample normalized quote response."""
    return {
        'regularMarketPrice': 605.23,
        'regularMarketChangePercent': 0.45,
        'volume': 45000000,
        'regularMarketOpen': 603.00,
        'regularMarketDayHigh': 607.50,
        'regularMarketDayLow': 602.10,
    }


@pytest.fixture
def sample_history_response():
    """Sample normalized history response."""
    return [
        {'date': '2026-01-30', 'close': 605.23},
        {'date': '2026-01-29', 'close': 602.15},
        {'date': '2026-01-28', 'close': 600.50},
        {'date': '2026-01-27', 'close': 598.75},
        {'date': '2026-01-24', 'close': 595.00},
    ]


# =============================================================================
# Utility Functions
# =============================================================================

def make_decimal(value):
    """Convert a value to Decimal for DynamoDB compatibility."""
    if value is None:
        return None
    return Decimal(str(value))
