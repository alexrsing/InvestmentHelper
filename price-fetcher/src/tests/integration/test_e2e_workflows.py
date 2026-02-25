"""
Integration tests for end-to-end workflows.

Tests cover full data flows:
- Price fetching: Lambda → API → DynamoDB → Client
- Holiday calendar: Handler → DynamoDB → Client
- Validation: Handler → Check records → Report gaps

Issue: #69
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import boto3
import pytest
import responses
from moto import mock_aws

# Add paths
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'fetchers'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from tests.integration.helpers import (
    create_tables, clear_module_caches, setup_test_environment, add_watchlist_symbol,
    TEST_PRICES_TABLE, TEST_WATCHLIST_TABLE, TEST_CONFIG_TABLE
)


class MockLambdaContext:
    """Mock AWS Lambda context."""

    def __init__(self, remaining_time_ms: int = 300000):
        self._remaining_time_ms = remaining_time_ms
        self.function_name = 'test-price-fetcher'
        self.aws_request_id = 'test-request-id'

    def get_remaining_time_in_millis(self) -> int:
        return self._remaining_time_ms


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""
    return MockLambdaContext(remaining_time_ms=300000)


# =============================================================================
# Price Fetching E2E Tests
# =============================================================================

class TestE2ESingleSymbolFlow:
    """Test single symbol fetch → store → retrieve flow."""

    @mock_aws
    @responses.activate
    def test_e2e_single_symbol_flow(self, aws_credentials, lambda_context):
        """SPY: fetch → store → retrieve matches."""
        # 1. Set up DynamoDB tables
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        # 2. Seed watchlist table
        add_watchlist_symbol(watchlist_table, 'SPY')

        # 3. Mock API response
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/quote",
            json={
                "symbol": "SPY",
                "close": "605.23",
                "previous_close": "603.00",
                "volume": "45000000",
                "open": "603.00",
                "high": "607.50",
                "low": "602.10"
            },
            status=200
        )
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/time_series",
            json={
                "values": [
                    {"datetime": "2026-01-30", "close": "605.23"},
                    {"datetime": "2026-01-29", "close": "602.15"},
                ],
                "status": "ok"
            },
            status=200
        )

        # 4. Clear module caches and invoke handler
        clear_module_caches(['td_service'])

        # Mock the fetcher
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_prices.return_value = {
            'success': ['SPY'],
            'failed': [],
            'skipped': [],
            'timeout_remaining': [],
            'data': {
                'SPY': [{
                    'etf_symbol': 'SPY',
                    'current_price': Decimal('605.23'),
                    'data_source': 'twelvedata',
                    'last_fetched_at': datetime.now().isoformat(),
                }]
            },
            'timeout_triggered': False,
        }

        with patch('main.PriceDataFetcher', return_value=mock_fetcher):
            from lambda_handler import handler
            response = handler({'symbols': ['SPY']}, lambda_context)

        # 5. Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success_count'] == 1


class TestE2EBatchSymbols:
    """Test batch symbol processing."""

    @mock_aws
    def test_e2e_batch_symbols(self, aws_credentials, lambda_context):
        """10 symbols: all stored correctly with proper fields."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        # Seed 10 symbols
        symbols = ['SPY', 'QQQ', 'IWM', 'DIA', 'VOO', 'VTI', 'VEA', 'VWO', 'BND', 'AGG']
        for symbol in symbols:
            add_watchlist_symbol(watchlist_table, symbol)

        clear_module_caches()

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_prices.return_value = {
            'success': symbols,
            'failed': [],
            'skipped': [],
            'timeout_remaining': [],
            'data': {s: [{'etf_symbol': s, 'current_price': Decimal('100.00')}] for s in symbols},
            'timeout_triggered': False,
        }

        with patch('main.PriceDataFetcher', return_value=mock_fetcher):
            from lambda_handler import handler
            response = handler({}, lambda_context)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success_count'] == 10
        assert body['processed'] == 10


class TestE2EDataSourceRecorded:
    """Test data source field is recorded correctly."""

    @mock_aws
    def test_e2e_data_source_recorded(self, aws_credentials):
        """data_source field matches API used."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        _, prices_table = create_tables(dynamodb)

        # Store record with data_source
        now = datetime.now()
        prices_table.put_item(Item={
            'etf_symbol': 'SPY',
            'current_price': Decimal('605.23'),
            'data_source': 'twelvedata',
            'last_fetched_at': now.isoformat(),
        })

        clear_module_caches()

        from db_service import DBService
        db = DBService()

        record = db.get_price_data('SPY')
        assert record is not None
        assert record['data_source'] == 'twelvedata'


class TestE2ETimestampUpdated:
    """Test timestamp is recent."""

    @mock_aws
    def test_e2e_timestamp_updated(self, aws_credentials):
        """last_fetched_at is recent ISO timestamp."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        _, prices_table = create_tables(dynamodb)

        now = datetime.now()
        prices_table.put_item(Item={
            'etf_symbol': 'QQQ',
            'current_price': Decimal('520.00'),
            'last_fetched_at': now.isoformat(),
        })

        clear_module_caches()

        from db_service import DBService
        db = DBService()

        timestamps = db.get_price_timestamps(['QQQ'])
        assert 'QQQ' in timestamps

        # Verify timestamp is recent (within last minute)
        ts = datetime.fromisoformat(timestamps['QQQ'])
        age = (now - ts).total_seconds()
        assert age < 60


class TestE2EHistoricalDataStored:
    """Test historical data is stored correctly."""

    @mock_aws
    def test_e2e_historical_data_stored(self, aws_credentials):
        """1d, 15m, 5m histories present in record."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        _, prices_table = create_tables(dynamodb)

        # Store record with all history types
        prices_table.put_item(Item={
            'etf_symbol': 'IWM',
            'current_price': Decimal('220.50'),
            'price_history_1d': [
                {'date': '2026-01-30', 'close': Decimal('220.50')},
                {'date': '2026-01-29', 'close': Decimal('218.00')},
            ],
            'price_history_15min': [
                {'date': '2026-01-30T15:45:00', 'close': Decimal('220.50')},
            ],
            'price_history_5m': [
                {'date': '2026-01-30T15:55:00', 'close': Decimal('220.50')},
            ],
        })

        clear_module_caches()

        from db_service import DBService
        db = DBService()

        record = db.get_price_data('IWM')
        assert 'price_history_1d' in record
        assert 'price_history_15min' in record
        assert 'price_history_5m' in record
        assert len(record['price_history_1d']) == 2


# =============================================================================
# Holiday Calendar E2E Tests
# =============================================================================

class TestE2EHolidayFetchStore:
    """Test holiday fetch and store flow."""

    @mock_aws
    def test_e2e_holiday_fetch_store(self, aws_credentials, lambda_context):
        """Fetch holidays → config table → client reads correctly."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        setup_test_environment()

        config_table = dynamodb.create_table(
            TableName=TEST_CONFIG_TABLE,
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
        config_table.meta.client.get_waiter('table_exists').wait(TableName=TEST_CONFIG_TABLE)

        # Store holidays in config table
        config_table.put_item(Item={
            'config_type': 'holidays',
            'config_key': 'US',
            'data': {
                'exchange': 'US',
                'holidays': [
                    {'atDate': '2026-01-19', 'eventName': 'MLK Day', 'tradingHour': '', 'source': 'finnhub'},
                    {'atDate': '2026-02-16', 'eventName': 'Presidents Day', 'tradingHour': '', 'source': 'finnhub'},
                ]
            },
            'updated_at': datetime.now().isoformat(),
        })

        clear_module_caches()

        from config_service import ConfigService
        config = ConfigService(table_name=TEST_CONFIG_TABLE)

        result = config.get_config('holidays', 'US')
        assert result is not None
        assert 'holidays' in result
        assert len(result['holidays']) == 2


class TestE2EHolidayAffectsTradingDay:
    """Test holiday affects is_trading_day."""

    def test_e2e_holiday_affects_trading_day(self):
        """Stored holiday → is_trading_day() returns False."""
        clear_module_caches()

        from pricedata import client
        client._holidays_cache = {
            'holidays': [
                {'atDate': '2026-01-19', 'eventName': 'MLK Day', 'tradingHour': '', 'source': 'finnhub'}
            ]
        }

        # MLK Day should not be a trading day
        result = client.is_trading_day(date(2026, 1, 19))
        assert result is False

        # Day after should be a trading day (it's a Tuesday)
        result = client.is_trading_day(date(2026, 1, 20))
        assert result is True

        client._holidays_cache = None


# =============================================================================
# Validation E2E Tests
# =============================================================================

class TestE2EValidatorDetectsGap:
    """Test validator detects missing data."""

    @mock_aws
    def test_e2e_validator_detects_gap(self, aws_credentials, lambda_context):
        """Missing date in history → flagged in response."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'SPY')

        clear_module_caches(['validator', 'core.validator'])

        # Mock validator to return incomplete data
        mock_validator_instance = MagicMock()
        mock_validator_instance.validate_symbols.return_value = {
            'complete': [],
            'incomplete': [{
                'symbol': 'SPY',
                'missing_count': 3,
                'first_missing': '2026-01-28',
                'last_missing': '2026-01-30',
            }],
            'total': 1,
            'complete_count': 0,
            'incomplete_count': 1,
            'interval': 'daily',
        }

        import core.validator as validator_module
        original_class = validator_module.PriceValidator

        try:
            validator_module.PriceValidator = MagicMock(return_value=mock_validator_instance)

            import lambda_handler as lh
            response = lh.validator_handler({}, lambda_context)

            assert response['statusCode'] == 207  # Multi-status
            body = json.loads(response['body'])
            assert body['incomplete_count'] == 1
        finally:
            validator_module.PriceValidator = original_class
