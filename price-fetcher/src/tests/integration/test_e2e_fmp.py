"""
Integration tests for Financial Modeling Prep end-to-end flows.

Tests the complete flow: Lambda → FMP API → DynamoDB → Client
with data_source=fmp.

Issue: #76
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
# FMP E2E Tests
# =============================================================================

class TestE2EFMPGetInfoStoresCorrectly:
    """Test quote data is stored with correct fields."""

    @mock_aws
    @responses.activate
    def test_e2e_fmp_get_info_stores_correctly(self, aws_credentials, lambda_context):
        """Quote data stored with correct fields via FMP."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'SPY')

        # Mock FMP quote endpoint (returns list)
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/quote",
            json=[{
                "symbol": "SPY",
                "price": 605.23,
                "changesPercentage": 0.3699,
                "change": 2.23,
                "dayLow": 602.10,
                "dayHigh": 607.50,
                "yearHigh": 620.00,
                "yearLow": 500.00,
                "marketCap": 500000000000,
                "priceAvg50": 595.00,
                "priceAvg200": 580.00,
                "volume": 45000000,
                "avgVolume": 40000000,
                "open": 603.00,
                "previousClose": 603.00
            }],
            status=200
        )

        # Mock historical data for 1d interval (uses /full endpoint)
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/historical-price-eod/full",
            json={"historical": [
                {"date": "2026-01-30", "close": 605.23},
                {"date": "2026-01-29", "close": 602.15},
            ]},
            status=200
        )

        # Mock 15m interval (uses /historical-chart/15min)
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/historical-chart/15min",
            json=[
                {"date": "2026-01-30 15:00:00", "close": 605.23},
                {"date": "2026-01-30 14:45:00", "close": 605.15},
            ],
            status=200
        )

        # Mock 5m interval (uses /historical-chart/5min)
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/historical-chart/5min",
            json=[
                {"date": "2026-01-30 15:00:00", "close": 605.23},
                {"date": "2026-01-30 14:55:00", "close": 605.20},
            ],
            status=200
        )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'fmp'
        os.environ['FMP_API_KEY'] = 'test-fmp-key'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='fmp')
            db_service = DBService()

            with patch('fmp_service.time.sleep'):
                results = fetcher.fetch_prices(['SPY'], context=lambda_context, db_service=db_service)

            assert 'SPY' in results['success']
            assert results['sources_used'].get('fmp', 0) == 1

            record = prices_table.get_item(Key={'etf_symbol': 'SPY'}).get('Item')
            assert record is not None
            assert record['etf_symbol'] == 'SPY'
            assert record['current_price'] == Decimal('605.23')
            assert record['data_source'] == 'fmp'

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('FMP_API_KEY', None)


class TestE2EFMPHistorical1d:
    """Test daily history storage."""

    @mock_aws
    @responses.activate
    def test_e2e_fmp_historical_1d(self, aws_credentials, lambda_context):
        """Daily history (1mo) stored in price_history_1d via FMP."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'QQQ')

        # Mock quote
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/quote",
            json=[{"symbol": "QQQ", "price": 420.50, "changesPercentage": 0.60, "volume": 30000000}],
            status=200
        )

        # Mock historical data for 1d interval (uses /full endpoint)
        daily_data = [
            {"date": f"2026-01-{30-i:02d}", "close": 420.50 - i*2}
            for i in range(10)
        ]
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/historical-price-eod/full",
            json={"historical": daily_data},
            status=200
        )

        # Mock 15m interval (uses /historical-chart/15min)
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/historical-chart/15min",
            json=[{"date": "2026-01-30 15:00:00", "close": 420.50}],
            status=200
        )

        # Mock 5m interval (uses /historical-chart/5min)
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/historical-chart/5min",
            json=[{"date": "2026-01-30 15:00:00", "close": 420.50}],
            status=200
        )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'fmp'
        os.environ['FMP_API_KEY'] = 'test-fmp-key'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='fmp')
            db_service = DBService()

            with patch('fmp_service.time.sleep'):
                results = fetcher.fetch_prices(['QQQ'], context=lambda_context, db_service=db_service)

            assert 'QQQ' in results['success']

            record = prices_table.get_item(Key={'etf_symbol': 'QQQ'}).get('Item')
            assert record is not None
            assert 'price_history_1d' in record
            assert len(record['price_history_1d']) == 10

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('FMP_API_KEY', None)


class TestE2EFMPHistoricalIntraday:
    """Test intraday history storage."""

    @mock_aws
    @responses.activate
    def test_e2e_fmp_historical_intraday(self, aws_credentials, lambda_context):
        """Intraday history stored via FMP."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'IWM')

        # Mock quote
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/quote",
            json=[{"symbol": "IWM", "price": 200.00, "changesPercentage": 0.76, "volume": 20000000}],
            status=200
        )

        # Mock daily (uses /full endpoint)
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/historical-price-eod/full",
            json={"historical": [{"date": "2026-01-30", "close": 200.00}]},
            status=200
        )

        # Mock 15m intraday (uses /historical-chart/15min)
        intraday_15m = [
            {"date": f"2026-01-30 {15-i//4}:{(i%4)*15:02d}:00", "close": 200.00 - i*0.25}
            for i in range(15)
        ]
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/historical-chart/15min",
            json=intraday_15m,
            status=200
        )

        # Mock 5m intraday (uses /historical-chart/5min)
        intraday_5m = [
            {"date": f"2026-01-30 15:{i*5:02d}:00", "close": 200.00 - i*0.10}
            for i in range(12)
        ]
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/historical-chart/5min",
            json=intraday_5m,
            status=200
        )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'fmp'
        os.environ['FMP_API_KEY'] = 'test-fmp-key'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='fmp')
            db_service = DBService()

            with patch('fmp_service.time.sleep'):
                results = fetcher.fetch_prices(['IWM'], context=lambda_context, db_service=db_service)

            assert 'IWM' in results['success']

            record = prices_table.get_item(Key={'etf_symbol': 'IWM'}).get('Item')
            assert record is not None
            assert 'price_history_15min' in record
            assert 'price_history_5m' in record

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('FMP_API_KEY', None)


class TestE2EFMPEmptyResponseSkipped:
    """Test that empty response is handled correctly."""

    @mock_aws
    @responses.activate
    def test_e2e_fmp_empty_response_skipped(self, aws_credentials, lambda_context):
        """Symbol with empty quote response is skipped."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'UNKNOWN')

        # Mock quote with empty list
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/quote",
            json=[],
            status=200
        )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'fmp'
        os.environ['FMP_API_KEY'] = 'test-fmp-key'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='fmp')
            db_service = DBService()

            with patch('fmp_service.time.sleep'):
                results = fetcher.fetch_prices(['UNKNOWN'], context=lambda_context, db_service=db_service)

            # Symbol should be skipped
            assert 'UNKNOWN' in results['skipped']
            assert 'UNKNOWN' not in results['success']

            # Nothing stored
            record = prices_table.get_item(Key={'etf_symbol': 'UNKNOWN'}).get('Item')
            assert record is None

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('FMP_API_KEY', None)


class TestE2EFMPClientReadsStoredData:
    """Test client API can read stored FMP prices."""

    @mock_aws
    def test_e2e_fmp_client_reads_stored_data(self, aws_credentials):
        """Client API can read prices stored via FMP."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        _, prices_table = create_tables(dynamodb)

        prices_table.put_item(Item={
            'etf_symbol': 'BND',
            'current_price': Decimal('72.50'),
            'data_source': 'fmp',
            'last_fetched_at': datetime.now().isoformat(),
            'price_history_1d': [
                {'date': '2026-01-30', 'close': Decimal('72.50')},
                {'date': '2026-01-29', 'close': Decimal('72.25')},
            ]
        })

        clear_module_caches()

        from pricedata.db_service import DBService

        client_db = DBService()
        data = client_db.get_price_data('BND')

        assert data is not None
        assert float(data['current_price']) == 72.50
        assert data['data_source'] == 'fmp'
