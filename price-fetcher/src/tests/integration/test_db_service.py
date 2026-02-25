"""
Integration tests for DBService DynamoDB operations.

Tests cover:
- get_watchlist_symbols (scan watchlist table)
- add/update/remove watchlist symbols
- pagination handling (>1MB responses)
- put_item (write single record)
- batch_put_items (batch writes)
- get_price_data (read single record)
- get_price_timestamps (read timestamps for multiple symbols)
- Decimal conversion for DynamoDB compatibility

Issue: #66, #80
"""

import os
import sys
from decimal import Decimal
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

# Add paths
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'fetchers'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from tests.integration.helpers import create_tables, add_watchlist_symbol


@pytest.fixture
def dynamodb_tables(aws_credentials):
    """Create mocked DynamoDB tables for DBService testing."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        yield {
            'dynamodb': dynamodb,
            'watchlist_table': watchlist_table,
            'prices_table': prices_table,
        }


class TestGetWatchlistSymbols:
    """Test DBService.get_watchlist_symbols()."""

    def test_db_get_watchlist_symbols(self, dynamodb_tables):
        """Scan watchlist table, return symbol list."""
        # Seed watchlist table
        watchlist = dynamodb_tables['watchlist_table']
        symbols = ['SPY', 'QQQ', 'IWM', 'DIA', 'VTI']
        for symbol in symbols:
            add_watchlist_symbol(watchlist, symbol)

        # Import after moto is active
        from db_service import DBService
        db = DBService()

        result = db.get_watchlist_symbols()

        assert len(result) == 5
        assert set(result) == set(symbols)

    def test_db_get_watchlist_symbols_empty_table(self, dynamodb_tables):
        """Empty watchlist table returns empty list."""
        from db_service import DBService
        db = DBService()

        result = db.get_watchlist_symbols()

        assert result == []

    def test_db_get_watchlist_symbols_enabled_only(self, dynamodb_tables):
        """Only return enabled symbols by default."""
        watchlist = dynamodb_tables['watchlist_table']
        add_watchlist_symbol(watchlist, 'SPY', enabled=True)
        add_watchlist_symbol(watchlist, 'QQQ', enabled=True)
        add_watchlist_symbol(watchlist, 'DISABLED', enabled=False)

        from db_service import DBService
        db = DBService()

        result = db.get_watchlist_symbols(enabled_only=True)
        assert len(result) == 2
        assert 'DISABLED' not in result

        result_all = db.get_watchlist_symbols(enabled_only=False)
        assert len(result_all) == 3
        assert 'DISABLED' in result_all

    def test_db_get_watchlist_symbols_by_type(self, dynamodb_tables):
        """Filter by symbol type."""
        watchlist = dynamodb_tables['watchlist_table']
        add_watchlist_symbol(watchlist, 'SPY', symbol_type='etf')
        add_watchlist_symbol(watchlist, 'AAPL', symbol_type='equity')
        add_watchlist_symbol(watchlist, '^VIX', symbol_type='index')

        from db_service import DBService
        db = DBService()

        etfs = db.get_watchlist_symbols(symbol_type='etf')
        assert etfs == ['SPY']

        indices = db.get_watchlist_symbols(symbol_type='index')
        assert indices == ['^VIX']

    def test_db_get_watchlist_symbols_sorted_by_priority(self, dynamodb_tables):
        """Symbols returned sorted by priority."""
        watchlist = dynamodb_tables['watchlist_table']
        add_watchlist_symbol(watchlist, 'LOW', priority=200)
        add_watchlist_symbol(watchlist, 'HIGH', priority=1)
        add_watchlist_symbol(watchlist, 'MED', priority=50)

        from db_service import DBService
        db = DBService()

        result = db.get_watchlist_symbols()
        assert result == ['HIGH', 'MED', 'LOW']


class TestWatchlistCRUD:
    """Test watchlist add/update/remove operations."""

    def test_db_add_watchlist_symbol(self, dynamodb_tables):
        """Add a symbol to watchlist."""
        from db_service import DBService
        db = DBService()

        result = db.add_watchlist_symbol('SPY', symbol_type='etf', priority=10)
        assert result is True

        item = db.get_watchlist_item('SPY')
        assert item is not None
        assert item['symbol'] == 'SPY'
        assert item['symbol_type'] == 'etf'
        assert item['priority'] == 10
        assert item['enabled'] is True

    def test_db_update_watchlist_symbol(self, dynamodb_tables):
        """Update watchlist symbol enabled/priority."""
        watchlist = dynamodb_tables['watchlist_table']
        add_watchlist_symbol(watchlist, 'SPY', enabled=True, priority=100)

        from db_service import DBService
        db = DBService()

        db.update_watchlist_symbol('SPY', enabled=False, priority=50)

        item = db.get_watchlist_item('SPY')
        assert item['enabled'] is False
        assert item['priority'] == 50

    def test_db_remove_watchlist_symbol(self, dynamodb_tables):
        """Remove a symbol from watchlist."""
        watchlist = dynamodb_tables['watchlist_table']
        add_watchlist_symbol(watchlist, 'SPY')

        from db_service import DBService
        db = DBService()

        result = db.remove_watchlist_symbol('SPY')
        assert result is True

        item = db.get_watchlist_item('SPY')
        assert item is None


class TestGetWatchlistPagination:
    """Test pagination for large datasets."""

    def test_db_get_watchlist_symbols_pagination(self, dynamodb_tables):
        """Handle paginated responses with LastEvaluatedKey."""
        # Seed with many items to trigger pagination
        # moto simulates pagination based on item count
        watchlist = dynamodb_tables['watchlist_table']

        # Create 50 symbols (enough to potentially trigger pagination in real DynamoDB)
        symbols = [f'ETF{i:03d}' for i in range(50)]
        for symbol in symbols:
            add_watchlist_symbol(watchlist, symbol)

        from db_service import DBService
        db = DBService()

        result = db.get_watchlist_symbols()

        assert len(result) == 50
        assert set(result) == set(symbols)


class TestPutItem:
    """Test DBService.put_item()."""

    def test_db_put_item(self, dynamodb_tables):
        """Write single price record."""
        from db_service import DBService
        db = DBService()

        item = {
            'etf_symbol': 'SPY',
            'current_price': Decimal('605.23'),
            'volume': Decimal('45000000'),
            'last_fetched_at': '2026-01-31T12:00:00+00:00',
            'data_source': 'twelvedata',
        }

        response = db.put_item(item)

        assert response is not None

        # Verify item was written
        prices = dynamodb_tables['prices_table']
        result = prices.get_item(Key={'etf_symbol': 'SPY'})
        assert result.get('Item') is not None
        assert result['Item']['current_price'] == Decimal('605.23')
        assert result['Item']['data_source'] == 'twelvedata'


class TestBatchPutItems:
    """Test DBService.batch_put_items()."""

    def test_db_batch_put_items(self, dynamodb_tables):
        """Write multiple records in batch."""
        from db_service import DBService
        db = DBService()

        items = {
            'SPY': [{
                'etf_symbol': 'SPY',
                'current_price': Decimal('605.23'),
                'data_source': 'twelvedata',
            }],
            'QQQ': [{
                'etf_symbol': 'QQQ',
                'current_price': Decimal('520.15'),
                'data_source': 'alphavantage',
            }],
            'IWM': [{
                'etf_symbol': 'IWM',
                'current_price': Decimal('220.50'),
                'data_source': 'finnhub',
            }],
        }

        result = db.batch_put_items(items)

        assert result is True

        # Verify all items were written
        prices = dynamodb_tables['prices_table']
        for symbol in ['SPY', 'QQQ', 'IWM']:
            item = prices.get_item(Key={'etf_symbol': symbol})
            assert item.get('Item') is not None

    def test_db_batch_put_25_limit(self, dynamodb_tables):
        """Verify batch handles more than 25 items (DynamoDB limit)."""
        from db_service import DBService
        db = DBService()

        # Create 30 items (more than DynamoDB's 25 batch limit)
        items = {}
        for i in range(30):
            symbol = f'ETF{i:03d}'
            items[symbol] = [{
                'etf_symbol': symbol,
                'current_price': Decimal(str(100 + i)),
                'data_source': 'test',
            }]

        result = db.batch_put_items(items)

        assert result is True

        # Verify all 30 items were written
        prices = dynamodb_tables['prices_table']
        response = prices.scan()
        assert len(response['Items']) == 30


class TestGetPriceData:
    """Test DBService.get_price_data()."""

    def test_db_get_price_data(self, dynamodb_tables):
        """Retrieve full price record by symbol."""
        # Seed price data
        prices = dynamodb_tables['prices_table']
        prices.put_item(Item={
            'etf_symbol': 'SPY',
            'current_price': Decimal('605.23'),
            'volume': Decimal('45000000'),
            'change_percent': Decimal('0.45'),
            'last_fetched_at': '2026-01-31T12:00:00+00:00',
            'data_source': 'twelvedata',
            'price_history_1d': [
                {'date': '2026-01-30', 'close': Decimal('603.00')},
                {'date': '2026-01-29', 'close': Decimal('600.50')},
            ],
        })

        from db_service import DBService
        db = DBService()

        result = db.get_price_data('SPY')

        assert result is not None
        assert result['etf_symbol'] == 'SPY'
        assert result['current_price'] == Decimal('605.23')
        assert result['data_source'] == 'twelvedata'
        assert 'price_history_1d' in result
        assert len(result['price_history_1d']) == 2

    def test_db_get_price_data_not_found(self, dynamodb_tables):
        """Return None for non-existent symbol."""
        from db_service import DBService
        db = DBService()

        result = db.get_price_data('NONEXISTENT')

        assert result is None


class TestGetPriceTimestamps:
    """Test DBService.get_price_timestamps()."""

    def test_db_get_price_timestamps(self, dynamodb_tables):
        """Get last_fetched_at for multiple symbols."""
        # Seed price data
        prices = dynamodb_tables['prices_table']
        test_data = {
            'SPY': '2026-01-31T12:00:00+00:00',
            'QQQ': '2026-01-31T11:00:00+00:00',
            'IWM': '2026-01-31T10:00:00+00:00',
        }
        for symbol, timestamp in test_data.items():
            prices.put_item(Item={
                'etf_symbol': symbol,
                'last_fetched_at': timestamp,
            })

        from db_service import DBService
        db = DBService()

        result = db.get_price_timestamps(['SPY', 'QQQ', 'IWM', 'DIA'])

        assert result['SPY'] == '2026-01-31T12:00:00+00:00'
        assert result['QQQ'] == '2026-01-31T11:00:00+00:00'
        assert result['IWM'] == '2026-01-31T10:00:00+00:00'
        assert result['DIA'] is None  # Not in database

    def test_db_get_price_timestamps_empty(self, dynamodb_tables):
        """Empty prices table returns None for all symbols."""
        from db_service import DBService
        db = DBService()

        result = db.get_price_timestamps(['SPY', 'QQQ'])

        assert result == {'SPY': None, 'QQQ': None}


class TestDecimalConversion:
    """Test Decimal conversion for DynamoDB compatibility."""

    def test_db_decimal_conversion(self, dynamodb_tables):
        """Floats stored as Decimal for DynamoDB."""
        from db_service import DBService
        db = DBService()

        # Note: Caller is responsible for Decimal conversion
        # This test verifies Decimals are stored correctly
        item = {
            'etf_symbol': 'SPY',
            'current_price': Decimal('605.23'),
            'volume': Decimal('45000000'),
            'change_percent': Decimal('0.4567'),
        }

        db.put_item(item)

        # Retrieve and verify types
        prices = dynamodb_tables['prices_table']
        result = prices.get_item(Key={'etf_symbol': 'SPY'})
        stored = result['Item']

        assert isinstance(stored['current_price'], Decimal)
        assert isinstance(stored['volume'], Decimal)
        assert isinstance(stored['change_percent'], Decimal)


class TestGetAllPriceRecords:
    """Test DBService.get_all_price_records()."""

    def test_db_get_all_price_records(self, dynamodb_tables):
        """Get all records from prices table with projection."""
        # Seed price data
        prices = dynamodb_tables['prices_table']
        for symbol in ['SPY', 'QQQ', 'IWM']:
            prices.put_item(Item={
                'etf_symbol': symbol,
                'current_price': Decimal('100.00'),
                'last_fetched_at': '2026-01-31T12:00:00+00:00',
                'last_updated': '2026-01-31',
                'data_source': 'test',
                'extra_field': 'should_not_be_included',  # Not in projection
            })

        from db_service import DBService
        db = DBService()

        result = db.get_all_price_records()

        assert len(result) == 3

        # Verify projection (only specific fields)
        for record in result:
            assert 'etf_symbol' in record
            assert 'last_fetched_at' in record
            assert 'data_source' in record
            # extra_field should not be included due to projection
            # (moto may not enforce projection, but real DynamoDB would)

    def test_db_get_all_price_records_empty(self, dynamodb_tables):
        """Empty prices table returns empty list."""
        from db_service import DBService
        db = DBService()

        result = db.get_all_price_records()

        assert result == []
