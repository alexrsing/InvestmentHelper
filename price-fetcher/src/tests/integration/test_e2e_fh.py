"""
Integration tests for Finnhub end-to-end flows.

Tests the complete flow: Lambda → Finnhub API → DynamoDB → Client
with data_source=finnhub.

Issue: #75
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


from tests.integration.helpers import create_tables, clear_module_caches, add_watchlist_symbol, TEST_PRICES_TABLE


# =============================================================================
# Finnhub E2E Tests
# =============================================================================

class TestE2EFHGetInfoStoresCorrectly:
    """Test quote data is stored with correct fields."""

    @mock_aws
    @responses.activate
    def test_e2e_fh_get_info_stores_correctly(self, aws_credentials, lambda_context):
        """Quote data stored with correct fields via Finnhub."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'SPY')

        # Mock Finnhub quote endpoint
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/quote",
            json={
                "c": 605.23,      # Current price
                "d": 2.23,        # Change
                "dp": 0.3699,     # Percent change
                "h": 607.50,      # High
                "l": 602.10,      # Low
                "o": 603.00,      # Open
                "pc": 603.00,     # Previous close
                "t": 1738267200   # Timestamp
            },
            status=200
        )

        # Mock stock/candle for historical data (3 intervals)
        now = datetime.now()
        for _ in range(3):
            responses.add(
                responses.GET,
                "https://finnhub.io/api/v1/stock/candle",
                json={
                    "s": "ok",
                    "c": [600.50, 602.15, 605.23],
                    "t": [
                        int((now - timedelta(days=2)).timestamp()),
                        int((now - timedelta(days=1)).timestamp()),
                        int(now.timestamp())
                    ]
                },
                status=200
            )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'finnhub'
        os.environ['FINNHUB_API_KEY'] = 'test-fh-key'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='finnhub')
            db_service = DBService()

            with patch('fh_service.time.sleep'):
                results = fetcher.fetch_prices(['SPY'], context=lambda_context, db_service=db_service)

            assert 'SPY' in results['success']
            assert results['sources_used'].get('finnhub', 0) == 1

            record = prices_table.get_item(Key={'etf_symbol': 'SPY'}).get('Item')
            assert record is not None
            assert record['etf_symbol'] == 'SPY'
            assert record['current_price'] == Decimal('605.23')
            assert record['data_source'] == 'finnhub'

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('FINNHUB_API_KEY', None)


class TestE2EFHHistorical1d:
    """Test daily history storage."""

    @mock_aws
    @responses.activate
    def test_e2e_fh_historical_1d(self, aws_credentials, lambda_context):
        """Daily history (1mo) stored in price_history_1d via Finnhub."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'QQQ')

        # Mock quote
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/quote",
            json={"c": 420.50, "d": 2.50, "dp": 0.60, "pc": 418.00},
            status=200
        )

        # Mock candle for 1d interval with 10 days
        now = datetime.now()
        closes = [420.50 - i*2 for i in range(10)]
        timestamps = [int((now - timedelta(days=i)).timestamp()) for i in range(10)]

        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/stock/candle",
            json={"s": "ok", "c": closes, "t": timestamps},
            status=200
        )

        # Mock for 15m and 5m intervals
        for _ in range(2):
            responses.add(
                responses.GET,
                "https://finnhub.io/api/v1/stock/candle",
                json={"s": "ok", "c": [420.50], "t": [int(now.timestamp())]},
                status=200
            )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'finnhub'
        os.environ['FINNHUB_API_KEY'] = 'test-fh-key'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='finnhub')
            db_service = DBService()

            with patch('fh_service.time.sleep'):
                results = fetcher.fetch_prices(['QQQ'], context=lambda_context, db_service=db_service)

            assert 'QQQ' in results['success']

            record = prices_table.get_item(Key={'etf_symbol': 'QQQ'}).get('Item')
            assert record is not None
            assert 'price_history_1d' in record
            assert len(record['price_history_1d']) == 10

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('FINNHUB_API_KEY', None)


class TestE2EFHHistoricalIntraday:
    """Test intraday history storage."""

    @mock_aws
    @responses.activate
    def test_e2e_fh_historical_intraday(self, aws_credentials, lambda_context):
        """15-minute and 5-minute history stored via Finnhub."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'IWM')

        # Mock quote
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/quote",
            json={"c": 200.00, "d": 1.50, "dp": 0.76, "pc": 198.50},
            status=200
        )

        now = datetime.now()

        # Mock candle for 1d interval
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/stock/candle",
            json={"s": "ok", "c": [200.00], "t": [int(now.timestamp())]},
            status=200
        )

        # Mock 15m candle with 15 data points
        closes_15m = [200.00 - i*0.25 for i in range(15)]
        timestamps_15m = [int((now - timedelta(minutes=i*15)).timestamp()) for i in range(15)]
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/stock/candle",
            json={"s": "ok", "c": closes_15m, "t": timestamps_15m},
            status=200
        )

        # Mock 5m candle with 12 data points
        closes_5m = [200.00 - i*0.10 for i in range(12)]
        timestamps_5m = [int((now - timedelta(minutes=i*5)).timestamp()) for i in range(12)]
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/stock/candle",
            json={"s": "ok", "c": closes_5m, "t": timestamps_5m},
            status=200
        )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'finnhub'
        os.environ['FINNHUB_API_KEY'] = 'test-fh-key'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='finnhub')
            db_service = DBService()

            with patch('fh_service.time.sleep'):
                results = fetcher.fetch_prices(['IWM'], context=lambda_context, db_service=db_service)

            assert 'IWM' in results['success']

            record = prices_table.get_item(Key={'etf_symbol': 'IWM'}).get('Item')
            assert record is not None
            assert 'price_history_15min' in record
            assert len(record['price_history_15min']) == 15
            assert 'price_history_5m' in record
            assert len(record['price_history_5m']) == 12

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('FINNHUB_API_KEY', None)


class TestE2EFHZeroPriceSkipped:
    """Test that zero price symbols are skipped."""

    @mock_aws
    @responses.activate
    def test_e2e_fh_zero_price_skipped(self, aws_credentials, lambda_context):
        """Symbol with zero price is skipped, not stored."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'DELISTED')

        # Mock quote with zero price
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/quote",
            json={"c": 0, "d": 0, "dp": 0, "h": 0, "l": 0, "o": 0, "pc": 0},
            status=200
        )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'finnhub'
        os.environ['FINNHUB_API_KEY'] = 'test-fh-key'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='finnhub')
            db_service = DBService()

            with patch('fh_service.time.sleep'):
                results = fetcher.fetch_prices(['DELISTED'], context=lambda_context, db_service=db_service)

            # Symbol should be skipped, not in success
            assert 'DELISTED' in results['skipped']
            assert 'DELISTED' not in results['success']

            # Nothing stored
            record = prices_table.get_item(Key={'etf_symbol': 'DELISTED'}).get('Item')
            assert record is None

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('FINNHUB_API_KEY', None)


class TestE2EFHClientReadsStoredData:
    """Test client API can read stored Finnhub prices."""

    @mock_aws
    def test_e2e_fh_client_reads_stored_data(self, aws_credentials):
        """Client API can read prices stored via Finnhub."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        _, prices_table = create_tables(dynamodb)

        prices_table.put_item(Item={
            'etf_symbol': 'VEA',
            'current_price': Decimal('48.75'),
            'data_source': 'finnhub',
            'last_fetched_at': datetime.now().isoformat(),
            'price_history_1d': [
                {'date': '2026-01-30', 'close': Decimal('48.75')},
                {'date': '2026-01-29', 'close': Decimal('48.50')},
            ]
        })

        clear_module_caches()

        from pricedata.db_service import DBService

        client_db = DBService()
        data = client_db.get_price_data('VEA')

        assert data is not None
        assert float(data['current_price']) == 48.75
        assert data['data_source'] == 'finnhub'
