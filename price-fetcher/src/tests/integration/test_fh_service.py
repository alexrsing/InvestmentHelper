"""
Integration tests for Finnhub service.

Tests cover:
- get_info success and failure cases
- get_historical_data (stock/candle)
- get_market_holidays
- Rate limiting

Issue: #64
"""

import json
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import responses

# Add fetchers to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'fetchers'))


@pytest.fixture
def fh_service():
    """Create FinnhubService with test API key."""
    from fh_service import FinnhubService
    return FinnhubService(api_key='test-api-key-12345', tier='free')


@pytest.fixture
def fh_quote_response():
    """Sample successful quote response."""
    return {
        "c": 605.23,      # Current price
        "d": 2.23,        # Change
        "dp": 0.3699,     # Percent change
        "h": 607.50,      # High
        "l": 602.10,      # Low
        "o": 603.00,      # Open
        "pc": 603.00,     # Previous close
        "t": 1738267200   # Timestamp
    }


@pytest.fixture
def fh_candle_response():
    """Sample successful candle response."""
    now = datetime.now()
    return {
        "s": "ok",
        "c": [600.50, 602.15, 605.23],  # Close prices
        "h": [601.00, 603.50, 607.50],  # High prices
        "l": [597.00, 599.00, 602.10],  # Low prices
        "o": [598.00, 600.00, 603.00],  # Open prices
        "v": [38000000, 42000000, 45000000],  # Volumes
        "t": [
            int((now - timedelta(days=2)).timestamp()),
            int((now - timedelta(days=1)).timestamp()),
            int(now.timestamp())
        ]
    }


# =============================================================================
# Quote Tests
# =============================================================================

class TestFHGetInfoSuccess:
    """Test successful quote fetching."""

    @responses.activate
    def test_fh_get_info_success(self, fh_service, fh_quote_response):
        """Fetch /quote, verify price/change mapping."""
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/quote",
            json=fh_quote_response,
            status=200
        )

        result = fh_service.get_info("SPY")

        assert result is not None
        assert result['regularMarketPrice'] == 605.23
        assert result['regularMarketOpen'] == 603.0
        assert result['regularMarketDayHigh'] == 607.5
        assert result['regularMarketDayLow'] == 602.1
        assert result['regularMarketPreviousClose'] == 603.0
        assert abs(result['regularMarketChangePercent'] - 0.3699) < 0.001


class TestFHGetInfoNoVolume:
    """Test volume handling."""

    @responses.activate
    def test_fh_get_info_no_volume(self, fh_service, fh_quote_response):
        """Confirm volume returns None (API limitation)."""
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/quote",
            json=fh_quote_response,
            status=200
        )

        result = fh_service.get_info("SPY")

        assert result is not None
        assert result['volume'] is None


class TestFHGetInfoInvalidSymbol:
    """Test handling of invalid symbols."""

    @responses.activate
    def test_fh_get_info_invalid_symbol(self, fh_service):
        """Zero price response returns None."""
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/quote",
            json={"c": 0, "d": 0, "dp": 0, "h": 0, "l": 0, "o": 0, "pc": 0},
            status=200
        )

        result = fh_service.get_info("INVALID123")

        assert result is None


class TestFHGetInfo403:
    """Test handling of 403 forbidden."""

    @responses.activate
    def test_fh_get_info_forbidden(self, fh_service):
        """403 response returns None without retry."""
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/quote",
            status=403
        )

        result = fh_service.get_info("RESTRICTED")

        assert result is None
        assert len(responses.calls) == 1


# =============================================================================
# Historical Data Tests
# =============================================================================

class TestFHGetHistoricalCandles:
    """Test candle data fetching."""

    @responses.activate
    def test_fh_get_historical_candles(self, fh_service, fh_candle_response):
        """/stock/candle with resolution mapping."""
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/stock/candle",
            json=fh_candle_response,
            status=200
        )

        result = fh_service.get_historical_data("SPY", period="1mo", interval="1d")

        assert result is not None
        assert len(result) == 3

        # Check closes are correct
        assert result[0]['close'] == 600.50
        assert result[1]['close'] == 602.15
        assert result[2]['close'] == 605.23


class TestFHGetHistoricalNoData:
    """Test handling of no data response."""

    @responses.activate
    def test_fh_get_historical_no_data(self, fh_service):
        """s='no_data' returns None."""
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/stock/candle",
            json={"s": "no_data"},
            status=200
        )

        result = fh_service.get_historical_data("INVALID", period="1mo", interval="1d")

        assert result is None


class TestFHGetHistoricalIntraday:
    """Test intraday data fetching."""

    @responses.activate
    def test_fh_get_historical_intraday_resolution(self, fh_service):
        """Verify resolution mapping for intraday intervals."""
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/stock/candle",
            json={"s": "ok", "c": [100.0], "t": [int(datetime.now().timestamp())]},
            status=200
        )

        # Test 15m interval
        fh_service.get_historical_data("SPY", period="1d", interval="15m")

        # Verify resolution=15 was passed
        request = responses.calls[0].request
        assert "resolution=15" in request.url


# =============================================================================
# Market Holidays Tests
# =============================================================================

class TestFHGetMarketHolidays:
    """Test market holidays endpoint."""

    @responses.activate
    def test_fh_get_market_holidays(self, fh_service):
        """/stock/market-holiday returns holiday list."""
        holidays_response = {
            "data": [
                {
                    "eventName": "Martin Luther King Jr. Day",
                    "atDate": "2026-01-19",
                    "tradingHour": ""
                },
                {
                    "eventName": "Day After Thanksgiving",
                    "atDate": "2026-11-27",
                    "tradingHour": "09:30-13:00"
                }
            ],
            "exchange": "US",
            "timezone": "America/New_York"
        }

        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/stock/market-holiday",
            json=holidays_response,
            status=200
        )

        result = fh_service.get_market_holidays("US")

        assert result is not None
        assert result['exchange'] == 'US'
        assert len(result['data']) == 2
        assert result['data'][0]['eventName'] == 'Martin Luther King Jr. Day'
        assert result['data'][1]['tradingHour'] == '09:30-13:00'


class TestFHGetMarketHolidaysError:
    """Test market holidays error handling."""

    @responses.activate
    def test_fh_get_market_holidays_error(self, fh_service):
        """API error returns None."""
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/stock/market-holiday",
            json={"error": "Invalid exchange"},
            status=200
        )

        result = fh_service.get_market_holidays("INVALID")

        assert result is None


# =============================================================================
# Rate Limit Tests
# =============================================================================

class TestFHRateLimitRetry:
    """Test rate limit handling."""

    @responses.activate
    def test_fh_rate_limit_retry(self, fh_service, fh_quote_response):
        """429 response triggers retry with backoff."""
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/quote",
            status=429
        )
        responses.add(
            responses.GET,
            "https://finnhub.io/api/v1/quote",
            json=fh_quote_response,
            status=200
        )

        with patch('fh_service.time.sleep'):
            result = fh_service.get_info("SPY")

        assert result is not None
        assert len(responses.calls) == 2


class TestFHTierLimits:
    """Test tier-specific rate limits."""

    def test_fh_tier_limits_free(self):
        """Free tier has 60/min."""
        from fh_service import FinnhubService
        service = FinnhubService(api_key='test-key', tier='free')

        assert service.calls_per_minute == 60

    def test_fh_tier_limits_paid(self):
        """Paid tier has 300/min."""
        from fh_service import FinnhubService
        service = FinnhubService(api_key='test-key', tier='paid')

        assert service.calls_per_minute == 300


class TestFHRemainingCalls:
    """Test remaining calls tracking."""

    def test_fh_get_remaining_calls(self):
        """Verify get_remaining_calls() returns correct info."""
        from fh_service import FinnhubService
        service = FinnhubService(api_key='test-key', tier='free')

        status = service.get_remaining_calls()

        assert status['tier'] == 'free'
        assert status['remaining_this_minute'] == 60
        assert status['calls_this_minute'] == 0
