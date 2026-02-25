"""
Integration tests for Twelve Data end-to-end flows.

Tests the complete flow: Lambda → Twelve Data API → DynamoDB → Client
with data_source=twelvedata.

Issue: #73
"""

import json
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import boto3
import pytest
import responses
from moto import mock_aws

# Add paths
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'fetchers'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from tests.integration.helpers import create_tables, clear_module_caches, add_watchlist_symbol


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
# Twelve Data E2E Tests
# =============================================================================

class TestE2ETDGetInfoStoresCorrectly:
    """Test quote data is stored with correct fields."""

    @mock_aws
    @responses.activate
    def test_e2e_td_get_info_stores_correctly(self, aws_credentials, lambda_context):
        """Quote data stored with correct fields via Twelve Data."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        # Seed watchlist
        add_watchlist_symbol(watchlist_table, 'SPY')

        # Mock Twelve Data quote endpoint
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
                "low": "602.10",
                "percent_change": "0.37"
            },
            status=200
        )

        # Mock time_series for historical data (called multiple times for different intervals)
        for _ in range(3):  # 1d, 15m, 5m intervals
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

        clear_module_caches()

        # Set environment for Twelve Data
        os.environ['DATA_SOURCE'] = 'twelvedata'
        os.environ['TWELVEDATA_API_KEY'] = 'test-td-key'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='twelvedata')
            db_service = DBService()

            with patch('td_service.time.sleep'):
                results = fetcher.fetch_prices(['SPY'], context=lambda_context, db_service=db_service)

            # Verify success
            assert 'SPY' in results['success']
            assert results['sources_used'].get('twelvedata', 0) == 1

            # Verify DynamoDB record
            record = prices_table.get_item(Key={'etf_symbol': 'SPY'}).get('Item')
            assert record is not None
            assert record['etf_symbol'] == 'SPY'
            assert record['current_price'] == Decimal('605.23')
            assert record['data_source'] == 'twelvedata'

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('TWELVEDATA_API_KEY', None)


class TestE2ETDHistorical1d:
    """Test daily history storage."""

    @mock_aws
    @responses.activate
    def test_e2e_td_historical_1d(self, aws_credentials, lambda_context):
        """Daily history (1mo) stored in price_history_1d."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'QQQ')

        # Mock quote
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/quote",
            json={
                "symbol": "QQQ",
                "close": "420.50",
                "previous_close": "418.00",
                "volume": "30000000"
            },
            status=200
        )

        # Mock time_series for 1d interval (this one should have more data)
        daily_data = [
            {"datetime": f"2026-01-{30-i:02d}", "close": str(420.50 - i*2)}
            for i in range(10)
        ]
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/time_series",
            json={"values": daily_data, "status": "ok"},
            status=200
        )

        # Mock for 15m and 5m intervals
        for _ in range(2):
            responses.add(
                responses.GET,
                "https://api.twelvedata.com/time_series",
                json={"values": [{"datetime": "2026-01-30 15:00:00", "close": "420.50"}], "status": "ok"},
                status=200
            )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'twelvedata'
        os.environ['TWELVEDATA_API_KEY'] = 'test-td-key'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='twelvedata')
            db_service = DBService()

            with patch('td_service.time.sleep'):
                results = fetcher.fetch_prices(['QQQ'], context=lambda_context, db_service=db_service)

            assert 'QQQ' in results['success']

            # Verify historical data stored
            record = prices_table.get_item(Key={'etf_symbol': 'QQQ'}).get('Item')
            assert record is not None
            assert 'price_history_1d' in record
            assert len(record['price_history_1d']) == 10

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('TWELVEDATA_API_KEY', None)


class TestE2ETDHistorical15m:
    """Test 15-minute history storage."""

    @mock_aws
    @responses.activate
    def test_e2e_td_historical_15m(self, aws_credentials, lambda_context):
        """15-minute history stored in price_history_15min."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'IWM')

        # Mock quote
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/quote",
            json={"symbol": "IWM", "close": "200.00", "previous_close": "198.50", "volume": "20000000"},
            status=200
        )

        # Mock for 1d interval
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/time_series",
            json={"values": [{"datetime": "2026-01-30", "close": "200.00"}], "status": "ok"},
            status=200
        )

        # Mock 15m interval data
        intraday_15m = [
            {"datetime": f"2026-01-30 {15-i//4}:{(i%4)*15:02d}:00", "close": str(200.00 - i*0.25)}
            for i in range(20)
        ]
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/time_series",
            json={"values": intraday_15m, "status": "ok"},
            status=200
        )

        # Mock for 5m interval
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/time_series",
            json={"values": [{"datetime": "2026-01-30 15:00:00", "close": "200.00"}], "status": "ok"},
            status=200
        )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'twelvedata'
        os.environ['TWELVEDATA_API_KEY'] = 'test-td-key'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='twelvedata')
            db_service = DBService()

            with patch('td_service.time.sleep'):
                results = fetcher.fetch_prices(['IWM'], context=lambda_context, db_service=db_service)

            assert 'IWM' in results['success']

            record = prices_table.get_item(Key={'etf_symbol': 'IWM'}).get('Item')
            assert record is not None
            assert 'price_history_15min' in record
            assert len(record['price_history_15min']) == 20

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('TWELVEDATA_API_KEY', None)


class TestE2ETDHistorical5m:
    """Test 5-minute history storage."""

    @mock_aws
    @responses.activate
    def test_e2e_td_historical_5m(self, aws_credentials, lambda_context):
        """5-minute history stored in price_history_5m."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'DIA')

        # Mock quote
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/quote",
            json={"symbol": "DIA", "close": "380.00", "previous_close": "378.00", "volume": "5000000"},
            status=200
        )

        # Mock for 1d and 15m intervals
        for _ in range(2):
            responses.add(
                responses.GET,
                "https://api.twelvedata.com/time_series",
                json={"values": [{"datetime": "2026-01-30", "close": "380.00"}], "status": "ok"},
                status=200
            )

        # Mock 5m interval data
        intraday_5m = [
            {"datetime": f"2026-01-30 15:{i*5:02d}:00", "close": str(380.00 - i*0.10)}
            for i in range(12)
        ]
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/time_series",
            json={"values": intraday_5m, "status": "ok"},
            status=200
        )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'twelvedata'
        os.environ['TWELVEDATA_API_KEY'] = 'test-td-key'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='twelvedata')
            db_service = DBService()

            with patch('td_service.time.sleep'):
                results = fetcher.fetch_prices(['DIA'], context=lambda_context, db_service=db_service)

            assert 'DIA' in results['success']

            record = prices_table.get_item(Key={'etf_symbol': 'DIA'}).get('Item')
            assert record is not None
            assert 'price_history_5m' in record
            assert len(record['price_history_5m']) == 12

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('TWELVEDATA_API_KEY', None)


class TestE2ETDClientReadsStoredData:
    """Test client API can read stored Twelve Data prices."""

    @mock_aws
    def test_e2e_td_client_reads_stored_data(self, aws_credentials):
        """Client API can read prices stored via Twelve Data."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        _, prices_table = create_tables(dynamodb)

        # Directly store a record as if Twelve Data fetched it
        prices_table.put_item(Item={
            'etf_symbol': 'VOO',
            'current_price': Decimal('500.75'),
            'data_source': 'twelvedata',
            'last_fetched_at': datetime.now().isoformat(),
            'price_history_1d': [
                {'date': '2026-01-30', 'close': Decimal('500.75')},
                {'date': '2026-01-29', 'close': Decimal('498.50')},
            ]
        })

        clear_module_caches()

        # Use the client to read the data
        from pricedata.db_service import DBService

        client_db = DBService()
        data = client_db.get_price_data('VOO')

        assert data is not None
        assert float(data['current_price']) == 500.75
        assert data['data_source'] == 'twelvedata'
