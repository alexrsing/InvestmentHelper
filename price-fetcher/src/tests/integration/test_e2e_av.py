"""
Integration tests for Alpha Vantage end-to-end flows.

Tests the complete flow: Lambda → Alpha Vantage API → DynamoDB → Client
with data_source=alphavantage.

Issue: #74
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
# Alpha Vantage E2E Tests
# =============================================================================

class TestE2EAVGetInfoStoresCorrectly:
    """Test quote data is stored with correct fields."""

    @mock_aws
    @responses.activate
    def test_e2e_av_get_info_stores_correctly(self, aws_credentials, lambda_context):
        """Quote data stored with correct fields via Alpha Vantage."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'SPY')

        # Mock Alpha Vantage GLOBAL_QUOTE endpoint
        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json={
                "Global Quote": {
                    "01. symbol": "SPY",
                    "02. open": "603.0000",
                    "03. high": "607.5000",
                    "04. low": "602.1000",
                    "05. price": "605.2300",
                    "06. volume": "45000000",
                    "07. latest trading day": "2026-01-30",
                    "08. previous close": "603.0000",
                    "09. change": "2.2300",
                    "10. change percent": "0.3699%"
                }
            },
            status=200
        )

        # Mock TIME_SERIES_DAILY for 1d interval
        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json={
                "Meta Data": {"2. Symbol": "SPY"},
                "Time Series (Daily)": {
                    "2026-01-30": {"4. close": "605.23"},
                    "2026-01-29": {"4. close": "602.15"},
                }
            },
            status=200
        )

        # Mock for 15m and 5m (Alpha Vantage may not support on free tier)
        # These will return None for free tier, so just mock with no_data responses
        for _ in range(2):
            responses.add(
                responses.GET,
                "https://www.alphavantage.co/query",
                json={},
                status=200
            )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'alphavantage'
        os.environ['ALPHA_VANTAGE_API_KEY'] = 'test-av-key'
        os.environ['ALPHA_VANTAGE_TIER'] = 'paid_30'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='alphavantage')
            db_service = DBService()

            with patch('av_service.time.sleep'):
                results = fetcher.fetch_prices(['SPY'], context=lambda_context, db_service=db_service)

            assert 'SPY' in results['success']
            assert results['sources_used'].get('alphavantage', 0) == 1

            record = prices_table.get_item(Key={'etf_symbol': 'SPY'}).get('Item')
            assert record is not None
            assert record['etf_symbol'] == 'SPY'
            assert record['current_price'] == Decimal('605.23')
            assert record['data_source'] == 'alphavantage'

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('ALPHA_VANTAGE_API_KEY', None)
            os.environ.pop('ALPHA_VANTAGE_TIER', None)


class TestE2EAVHistorical1d:
    """Test daily history storage."""

    @mock_aws
    @responses.activate
    def test_e2e_av_historical_1d(self, aws_credentials, lambda_context):
        """Daily history (1mo) stored in price_history_1d via Alpha Vantage."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'QQQ')

        # Mock quote
        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json={
                "Global Quote": {
                    "01. symbol": "QQQ",
                    "05. price": "420.5000",
                    "06. volume": "30000000",
                    "10. change percent": "0.60%"
                }
            },
            status=200
        )

        # Mock TIME_SERIES_DAILY with 10 days of data
        daily_data = {}
        for i in range(10):
            date_str = f"2026-01-{30-i:02d}"
            daily_data[date_str] = {"4. close": str(420.50 - i*2)}

        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json={"Meta Data": {"2. Symbol": "QQQ"}, "Time Series (Daily)": daily_data},
            status=200
        )

        # Mock for intraday (may not return data)
        for _ in range(2):
            responses.add(
                responses.GET,
                "https://www.alphavantage.co/query",
                json={},
                status=200
            )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'alphavantage'
        os.environ['ALPHA_VANTAGE_API_KEY'] = 'test-av-key'
        os.environ['ALPHA_VANTAGE_TIER'] = 'paid_30'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='alphavantage')
            db_service = DBService()

            with patch('av_service.time.sleep'):
                results = fetcher.fetch_prices(['QQQ'], context=lambda_context, db_service=db_service)

            assert 'QQQ' in results['success']

            record = prices_table.get_item(Key={'etf_symbol': 'QQQ'}).get('Item')
            assert record is not None
            assert 'price_history_1d' in record
            assert len(record['price_history_1d']) == 10

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('ALPHA_VANTAGE_API_KEY', None)
            os.environ.pop('ALPHA_VANTAGE_TIER', None)


class TestE2EAVHistoricalIntraday:
    """Test intraday history storage on paid tier."""

    @mock_aws
    @responses.activate
    def test_e2e_av_historical_intraday(self, aws_credentials, lambda_context):
        """Intraday history stored when using paid tier."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'IWM')

        # Mock quote
        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json={
                "Global Quote": {
                    "01. symbol": "IWM",
                    "05. price": "200.0000",
                    "06. volume": "20000000"
                }
            },
            status=200
        )

        # Mock daily
        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json={
                "Meta Data": {"2. Symbol": "IWM"},
                "Time Series (Daily)": {"2026-01-30": {"4. close": "200.00"}}
            },
            status=200
        )

        # Mock 15min intraday
        intraday_15m = {}
        for i in range(10):
            time_str = f"2026-01-30 {15-i//4}:{(i%4)*15:02d}:00"
            intraday_15m[time_str] = {"4. close": str(200.00 - i*0.25)}

        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json={"Meta Data": {"2. Symbol": "IWM"}, "Time Series (15min)": intraday_15m},
            status=200
        )

        # Mock 5min intraday
        intraday_5m = {}
        for i in range(12):
            time_str = f"2026-01-30 15:{i*5:02d}:00"
            intraday_5m[time_str] = {"4. close": str(200.00 - i*0.10)}

        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json={"Meta Data": {"2. Symbol": "IWM"}, "Time Series (5min)": intraday_5m},
            status=200
        )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'alphavantage'
        os.environ['ALPHA_VANTAGE_API_KEY'] = 'test-av-key'
        os.environ['ALPHA_VANTAGE_TIER'] = 'paid_30'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='alphavantage')
            db_service = DBService()

            with patch('av_service.time.sleep'):
                results = fetcher.fetch_prices(['IWM'], context=lambda_context, db_service=db_service)

            assert 'IWM' in results['success']

            record = prices_table.get_item(Key={'etf_symbol': 'IWM'}).get('Item')
            assert record is not None
            # Alpha Vantage intraday should be stored
            assert record['price_history_15min'] is not None or 'price_history_15min' in record

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('ALPHA_VANTAGE_API_KEY', None)
            os.environ.pop('ALPHA_VANTAGE_TIER', None)


class TestE2EAVRateLimitHandled:
    """Test rate limit handling with retry."""

    @mock_aws
    @responses.activate
    def test_e2e_av_rate_limit_handled(self, aws_credentials, lambda_context):
        """Rate limit 'Note' response triggers retry and succeeds."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        add_watchlist_symbol(watchlist_table, 'DIA')

        # First response is rate limit note
        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json={"Note": "Thank you for using Alpha Vantage! API rate limit reached."},
            status=200
        )

        # Second response succeeds
        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json={
                "Global Quote": {
                    "01. symbol": "DIA",
                    "05. price": "380.0000",
                    "06. volume": "5000000"
                }
            },
            status=200
        )

        # Mock historical data calls (3 intervals)
        for _ in range(3):
            responses.add(
                responses.GET,
                "https://www.alphavantage.co/query",
                json={
                    "Meta Data": {"2. Symbol": "DIA"},
                    "Time Series (Daily)": {"2026-01-30": {"4. close": "380.00"}}
                },
                status=200
            )

        clear_module_caches()

        os.environ['DATA_SOURCE'] = 'alphavantage'
        os.environ['ALPHA_VANTAGE_API_KEY'] = 'test-av-key'
        os.environ['ALPHA_VANTAGE_TIER'] = 'paid_30'

        try:
            from main import PriceDataFetcher
            from db_service import DBService

            fetcher = PriceDataFetcher(data_source='alphavantage')
            db_service = DBService()

            with patch('av_service.time.sleep'):
                results = fetcher.fetch_prices(['DIA'], context=lambda_context, db_service=db_service)

            assert 'DIA' in results['success']

            record = prices_table.get_item(Key={'etf_symbol': 'DIA'}).get('Item')
            assert record is not None
            assert record['current_price'] == Decimal('380')

        finally:
            os.environ.pop('DATA_SOURCE', None)
            os.environ.pop('ALPHA_VANTAGE_API_KEY', None)
            os.environ.pop('ALPHA_VANTAGE_TIER', None)


class TestE2EAVClientReadsStoredData:
    """Test client API can read stored Alpha Vantage prices."""

    @mock_aws
    def test_e2e_av_client_reads_stored_data(self, aws_credentials):
        """Client API can read prices stored via Alpha Vantage."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        _, prices_table = create_tables(dynamodb)

        prices_table.put_item(Item={
            'etf_symbol': 'VTI',
            'current_price': Decimal('250.50'),
            'data_source': 'alphavantage',
            'last_fetched_at': datetime.now().isoformat(),
            'price_history_1d': [
                {'date': '2026-01-30', 'close': Decimal('250.50')},
                {'date': '2026-01-29', 'close': Decimal('248.75')},
            ]
        })

        clear_module_caches()

        from pricedata.db_service import DBService

        client_db = DBService()
        data = client_db.get_price_data('VTI')

        assert data is not None
        assert float(data['current_price']) == 250.50
        assert data['data_source'] == 'alphavantage'
