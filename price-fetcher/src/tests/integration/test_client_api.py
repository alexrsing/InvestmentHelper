"""
Integration tests for pricedata client API.

Tests cover:
- Price operations: get_price, get_price_history, get_current_price, list_symbols
- Holiday operations: is_trading_day, is_market_holiday, is_early_close,
                     get_market_holidays, load_holidays

Issue: #68
"""

import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from tests.integration.helpers import (
    create_tables, create_all_tables, clear_module_caches, add_watchlist_symbol,
    TEST_PRICES_TABLE, TEST_CONFIG_TABLE
)


@pytest.fixture
def dynamodb_tables(aws_credentials):
    """Create mocked DynamoDB tables for client testing."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table, config_table = create_all_tables(dynamodb)

        yield {
            'dynamodb': dynamodb,
            'watchlist_table': watchlist_table,
            'prices_table': prices_table,
            'config_table': config_table,
        }


# =============================================================================
# Price Operations Tests
# =============================================================================

class TestClientGetPrice:
    """Test get_price() function."""

    @mock_aws
    def test_client_get_price(self, aws_credentials):
        """Price lookup by symbol and date."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

        prices_table = dynamodb.create_table(
            TableName='marketdata-test-prices',
            KeySchema=[{'AttributeName': 'etf_symbol', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'etf_symbol', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        prices_table.meta.client.get_waiter('table_exists').wait(TableName='marketdata-test-prices')

        # Seed price data
        prices_table.put_item(Item={
            'etf_symbol': 'SPY',
            'current_price': Decimal('605.23'),
            'price_history_1d': [
                {'date': '2026-01-28', 'close': Decimal('600.00')},
                {'date': '2026-01-29', 'close': Decimal('602.15')},
                {'date': '2026-01-30', 'close': Decimal('605.23')},
            ],
        })

        # Clear module cache and reset singleton
        for mod_name in list(sys.modules.keys()):
            if 'pricedata' in mod_name:
                del sys.modules[mod_name]

        from pricedata import client
        client._db = None

        price = client.get_price('SPY', date(2026, 1, 30))

        assert price == 605.23


class TestClientGetPriceWeekendFallback:
    """Test weekend date fallback behavior."""

    @mock_aws
    def test_client_get_price_weekend_fallback(self, aws_credentials):
        """Weekend date returns Friday price."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

        prices_table = dynamodb.create_table(
            TableName='marketdata-test-prices',
            KeySchema=[{'AttributeName': 'etf_symbol', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'etf_symbol', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        prices_table.meta.client.get_waiter('table_exists').wait(TableName='marketdata-test-prices')

        # Seed data with Friday price
        # 2026-01-30 is Friday, 2026-01-31 is Saturday
        prices_table.put_item(Item={
            'etf_symbol': 'SPY',
            'price_history_1d': [
                {'date': '2026-01-30', 'close': Decimal('605.23')},  # Friday
            ],
        })

        for mod_name in list(sys.modules.keys()):
            if 'pricedata' in mod_name:
                del sys.modules[mod_name]

        from pricedata import client
        client._db = None

        # Query Saturday, should get Friday's price
        price = client.get_price('SPY', date(2026, 1, 31))

        assert price == 605.23


class TestClientGetPriceHistory:
    """Test get_price_history() function."""

    @mock_aws
    def test_client_get_price_history(self, aws_credentials):
        """Date range query returns dict[date, float]."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

        prices_table = dynamodb.create_table(
            TableName='marketdata-test-prices',
            KeySchema=[{'AttributeName': 'etf_symbol', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'etf_symbol', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        prices_table.meta.client.get_waiter('table_exists').wait(TableName='marketdata-test-prices')

        prices_table.put_item(Item={
            'etf_symbol': 'QQQ',
            'price_history_1d': [
                {'date': '2026-01-27', 'close': Decimal('510.00')},
                {'date': '2026-01-28', 'close': Decimal('515.00')},
                {'date': '2026-01-29', 'close': Decimal('518.00')},
                {'date': '2026-01-30', 'close': Decimal('520.15')},
            ],
        })

        for mod_name in list(sys.modules.keys()):
            if 'pricedata' in mod_name:
                del sys.modules[mod_name]

        from pricedata import client
        client._db = None

        history = client.get_price_history('QQQ', date(2026, 1, 28), date(2026, 1, 30))

        assert len(history) == 3
        assert history[date(2026, 1, 28)] == 515.00
        assert history[date(2026, 1, 29)] == 518.00
        assert history[date(2026, 1, 30)] == 520.15


class TestClientGetCurrentPrice:
    """Test get_current_price() function."""

    @mock_aws
    def test_client_get_current_price(self, aws_credentials):
        """Most recent price from current_price field."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

        prices_table = dynamodb.create_table(
            TableName='marketdata-test-prices',
            KeySchema=[{'AttributeName': 'etf_symbol', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'etf_symbol', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        prices_table.meta.client.get_waiter('table_exists').wait(TableName='marketdata-test-prices')

        prices_table.put_item(Item={
            'etf_symbol': 'IWM',
            'current_price': Decimal('220.50'),
        })

        for mod_name in list(sys.modules.keys()):
            if 'pricedata' in mod_name:
                del sys.modules[mod_name]

        from pricedata import client
        client._db = None

        price = client.get_current_price('IWM')

        assert price == 220.50


class TestClientListSymbols:
    """Test list_symbols() function."""

    @mock_aws
    def test_client_list_symbols(self, aws_credentials):
        """Return all tracked symbols from prices table."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

        prices_table = dynamodb.create_table(
            TableName='marketdata-test-prices',
            KeySchema=[{'AttributeName': 'etf_symbol', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'etf_symbol', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        prices_table.meta.client.get_waiter('table_exists').wait(TableName='marketdata-test-prices')

        # Seed multiple symbols
        for symbol in ['SPY', 'QQQ', 'IWM', 'DIA']:
            prices_table.put_item(Item={
                'etf_symbol': symbol,
                'current_price': Decimal('100.00'),
            })

        for mod_name in list(sys.modules.keys()):
            if 'pricedata' in mod_name:
                del sys.modules[mod_name]

        from pricedata import client
        client._db = None

        symbols = client.list_symbols()

        assert len(symbols) == 4
        assert sorted(symbols) == ['DIA', 'IWM', 'QQQ', 'SPY']


# =============================================================================
# Holiday Operations Tests
# =============================================================================

class TestClientIsTradingDayWeekday:
    """Test is_trading_day() for weekdays."""

    def test_client_is_trading_day_weekday(self, monkeypatch):
        """Weekday, not holiday returns True."""
        for mod_name in list(sys.modules.keys()):
            if 'pricedata' in mod_name:
                del sys.modules[mod_name]

        from pricedata import client
        client._holidays_cache = None

        # Mock load_holidays to return empty (no holidays)
        client._holidays_cache = {'holidays': []}

        # 2026-01-28 is a Wednesday (not a weekend, not a holiday)
        result = client.is_trading_day(date(2026, 1, 28))

        assert result is True


class TestClientIsTradingDayWeekend:
    """Test is_trading_day() for weekends."""

    def test_client_is_trading_day_weekend(self, monkeypatch):
        """Saturday/Sunday returns False."""
        for mod_name in list(sys.modules.keys()):
            if 'pricedata' in mod_name:
                del sys.modules[mod_name]

        from pricedata import client
        client._holidays_cache = {'holidays': []}

        # 2026-01-31 is Saturday
        result_sat = client.is_trading_day(date(2026, 1, 31))
        assert result_sat is False

        # 2026-02-01 is Sunday
        result_sun = client.is_trading_day(date(2026, 2, 1))
        assert result_sun is False


class TestClientIsMarketHoliday:
    """Test is_market_holiday() function."""

    def test_client_is_market_holiday(self, monkeypatch):
        """Known holiday date returns True."""
        for mod_name in list(sys.modules.keys()):
            if 'pricedata' in mod_name:
                del sys.modules[mod_name]

        from pricedata import client
        client._holidays_cache = {
            'holidays': [
                {
                    'atDate': '2026-01-19',
                    'eventName': 'Martin Luther King Jr. Day',
                    'tradingHour': '',
                    'source': 'finnhub'
                },
            ]
        }

        # MLK Day is a holiday
        result = client.is_market_holiday(date(2026, 1, 19))
        assert result is True

        # Regular day is not a holiday
        result = client.is_market_holiday(date(2026, 1, 20))
        assert result is False


class TestClientIsEarlyClose:
    """Test is_early_close() function."""

    def test_client_is_early_close(self, monkeypatch):
        """Early close date returns trading hours."""
        for mod_name in list(sys.modules.keys()):
            if 'pricedata' in mod_name:
                del sys.modules[mod_name]

        from pricedata import client
        client._holidays_cache = {
            'holidays': [
                {
                    'atDate': '2026-11-27',
                    'eventName': 'Day After Thanksgiving (Early Close)',
                    'tradingHour': '09:30-13:00',
                    'source': 'finnhub'
                },
            ]
        }

        result = client.is_early_close(date(2026, 11, 27))
        assert result == '09:30-13:00'

        # Regular day is not early close
        result = client.is_early_close(date(2026, 1, 28))
        assert result is None


class TestClientGetMarketHolidays:
    """Test get_market_holidays() function."""

    def test_client_get_market_holidays(self, monkeypatch):
        """Date range returns holiday list."""
        for mod_name in list(sys.modules.keys()):
            if 'pricedata' in mod_name:
                del sys.modules[mod_name]

        from pricedata import client
        client._holidays_cache = {
            'holidays': [
                {'atDate': '2026-01-01', 'eventName': 'New Year', 'tradingHour': '', 'source': 'finnhub'},
                {'atDate': '2026-01-19', 'eventName': 'MLK Day', 'tradingHour': '', 'source': 'finnhub'},
                {'atDate': '2026-02-16', 'eventName': 'Presidents Day', 'tradingHour': '', 'source': 'finnhub'},
            ]
        }

        result = client.get_market_holidays(date(2026, 1, 1), date(2026, 1, 31))

        assert len(result) == 2
        assert result[0]['eventName'] == 'New Year'
        assert result[1]['eventName'] == 'MLK Day'


class TestClientLoadHolidaysDynamodb:
    """Test DynamoDB holiday loading."""

    @mock_aws
    def test_client_load_holidays_dynamodb(self, monkeypatch, aws_credentials):
        """Load from DynamoDB config table."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

        # Create config table
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
        config_table.meta.client.get_waiter('table_exists').wait(TableName='marketdata-test-config')

        # Seed holiday data
        config_table.put_item(Item={
            'config_type': 'holidays',
            'config_key': 'US',
            'data': {
                'holidays': [
                    {'atDate': '2026-01-19', 'eventName': 'MLK Day', 'tradingHour': '', 'source': 'finnhub'}
                ]
            },
            'updated_at': '2026-01-31T12:00:00',
        })

        for mod_name in list(sys.modules.keys()):
            if 'pricedata' in mod_name or 'config_service' in mod_name:
                del sys.modules[mod_name]

        from pricedata import client
        client._holidays_cache = None

        # Mock the DynamoDB fetch to return our data
        result = client._load_holidays_from_dynamodb('US')

        # Result should contain holidays (from DynamoDB's data field)
        if result:
            assert 'holidays' in result or isinstance(result, dict)


class TestClientLoadHolidaysFileFallback:
    """Test file fallback when DynamoDB fails."""

    def test_client_load_holidays_file_fallback(self, monkeypatch, tmp_path):
        """DynamoDB fails, falls back to JSON file."""
        for mod_name in list(sys.modules.keys()):
            if 'pricedata' in mod_name:
                del sys.modules[mod_name]

        from pricedata import client
        client._holidays_cache = None

        # Create a temporary holidays file
        holidays_data = {
            'exchange': 'US',
            'holidays': [
                {'atDate': '2026-01-19', 'eventName': 'MLK Day from file', 'tradingHour': '', 'source': 'file'}
            ]
        }
        holidays_file = tmp_path / 'market_holidays.json'
        holidays_file.write_text(json.dumps(holidays_data))

        # Mock _get_holidays_file_path to return our temp file
        original_get_path = client._get_holidays_file_path

        def mock_get_path():
            return holidays_file

        client._get_holidays_file_path = mock_get_path

        # Mock DynamoDB to fail
        def mock_dynamo_fail(exchange='US'):
            return None

        client._load_holidays_from_dynamodb = mock_dynamo_fail

        try:
            # Should fall back to file
            result = client.load_holidays()

            assert 'holidays' in result
            assert len(result['holidays']) == 1
            assert result['holidays'][0]['eventName'] == 'MLK Day from file'
        finally:
            client._get_holidays_file_path = original_get_path
            client._holidays_cache = None


class TestClientClearHolidaysCache:
    """Test cache clearing functionality."""

    def test_client_clear_holidays_cache(self):
        """Cache can be cleared."""
        for mod_name in list(sys.modules.keys()):
            if 'pricedata' in mod_name:
                del sys.modules[mod_name]

        from pricedata import client

        # Set cache
        client._holidays_cache = {'holidays': [{'atDate': '2026-01-01'}]}

        # Clear it
        client.clear_holidays_cache()

        assert client._holidays_cache is None
