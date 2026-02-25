"""
Integration tests for Alpha Vantage service.

Tests cover:
- get_info success and rate limit handling
- get_historical_data with different intervals
- Tier-specific rate limits and intraday access
- Request tracking

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
def av_service():
    """Create AlphaVantageService with test API key."""
    from av_service import AlphaVantageService
    return AlphaVantageService(api_key='test-api-key-12345', tier='paid_30')


@pytest.fixture
def av_quote_response():
    """Sample successful GLOBAL_QUOTE response."""
    return {
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
    }


@pytest.fixture
def av_time_series_daily_response():
    """Sample TIME_SERIES_DAILY response."""
    return {
        "Meta Data": {
            "1. Information": "Daily Prices (open, high, low, close) and Volumes",
            "2. Symbol": "SPY",
            "3. Last Refreshed": "2026-01-30",
        },
        "Time Series (Daily)": {
            "2026-01-30": {"1. open": "603.00", "2. high": "607.50", "3. low": "602.10", "4. close": "605.23", "5. volume": "45000000"},
            "2026-01-29": {"1. open": "600.00", "2. high": "603.50", "3. low": "599.00", "4. close": "602.15", "5. volume": "42000000"},
            "2026-01-28": {"1. open": "598.00", "2. high": "601.00", "3. low": "597.00", "4. close": "600.50", "5. volume": "38000000"},
        }
    }


# =============================================================================
# Quote Tests
# =============================================================================

class TestAVGetInfoSuccess:
    """Test successful quote fetching."""

    @responses.activate
    def test_av_get_info_success(self, av_service, av_quote_response):
        """Fetch GLOBAL_QUOTE, verify field mapping."""
        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json=av_quote_response,
            status=200
        )

        result = av_service.get_info("SPY")

        assert result is not None
        assert result['regularMarketPrice'] == 605.23
        assert result['volume'] == 45000000
        assert result['regularMarketOpen'] == 603.0
        assert result['regularMarketDayHigh'] == 607.5
        assert result['regularMarketDayLow'] == 602.1
        assert result['regularMarketPreviousClose'] == 603.0
        assert abs(result['regularMarketChangePercent'] - 0.3699) < 0.001


class TestAVGetInfoRateLimited:
    """Test rate limit handling."""

    @responses.activate
    def test_av_get_info_rate_limited(self, av_service, av_quote_response):
        """Handle 'Note' response (rate limit message) with retry."""
        # First response is rate limit note
        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json={"Note": "Thank you for using Alpha Vantage! Our standard API rate limit is 25 requests per day."},
            status=200
        )
        # Second response is success
        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json=av_quote_response,
            status=200
        )

        with patch('av_service.time.sleep'):
            result = av_service.get_info("SPY")

        assert result is not None
        assert result['regularMarketPrice'] == 605.23
        assert len(responses.calls) == 2


class TestAVGetInfoEmptyQuote:
    """Test handling of empty quote response."""

    @responses.activate
    def test_av_get_info_empty_quote(self, av_service):
        """Empty Global Quote returns None."""
        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json={"Global Quote": {}},
            status=200
        )

        result = av_service.get_info("INVALID")

        assert result is None


# =============================================================================
# Historical Data Tests
# =============================================================================

class TestAVGetHistoricalDaily:
    """Test daily historical data."""

    @responses.activate
    def test_av_get_historical_daily(self, av_service, av_time_series_daily_response):
        """TIME_SERIES_DAILY to normalized format."""
        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json=av_time_series_daily_response,
            status=200
        )

        result = av_service.get_historical_data("SPY", period="1mo", interval="1d")

        assert result is not None
        assert len(result) == 3

        # Results in chronological order
        assert result[0]['date'] == '2026-01-28'
        assert result[0]['close'] == 600.50
        assert result[2]['date'] == '2026-01-30'
        assert result[2]['close'] == 605.23


class TestAVGetHistoricalIntraday:
    """Test intraday historical data."""

    @responses.activate
    def test_av_get_historical_intraday(self, av_service):
        """TIME_SERIES_INTRADAY with 15min."""
        intraday_response = {
            "Meta Data": {"1. Information": "Intraday (15min)", "2. Symbol": "SPY"},
            "Time Series (15min)": {
                "2026-01-30 15:45:00": {"4. close": "605.50"},
                "2026-01-30 15:30:00": {"4. close": "605.25"},
                "2026-01-30 15:15:00": {"4. close": "605.00"},
            }
        }

        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json=intraday_response,
            status=200
        )

        result = av_service.get_historical_data("SPY", period="1d", interval="15m")

        assert result is not None
        assert len(result) == 3

        # Verify chronological order
        assert result[0]['date'] == '2026-01-30 15:15:00'
        assert result[2]['date'] == '2026-01-30 15:45:00'


class TestAVIntradayFreeTier:
    """Test intraday access on free tier."""

    def test_av_intraday_blocked_on_free_tier(self):
        """Free tier cannot access intraday data."""
        from av_service import AlphaVantageService
        service = AlphaVantageService(api_key='test-key', tier='free')

        # Intraday should return None (not supported)
        result = service.get_historical_data("SPY", period="1d", interval="15m")

        assert result is None


# =============================================================================
# Rate Limit and Tier Tests
# =============================================================================

class TestAVTierRateLimits:
    """Test tier-specific rate limits."""

    def test_av_tier_limits_free(self):
        """Free tier has 5/min, 25/day."""
        from av_service import AlphaVantageService
        service = AlphaVantageService(api_key='test-key', tier='free')

        assert service.requests_per_minute == 5
        assert service.requests_per_day == 25
        assert service.supports_intraday is False

    def test_av_tier_limits_paid_30(self):
        """Paid 30 tier has 30/min, unlimited/day."""
        from av_service import AlphaVantageService
        service = AlphaVantageService(api_key='test-key', tier='paid_30')

        assert service.requests_per_minute == 30
        assert service.requests_per_day is None
        assert service.supports_intraday is True

    def test_av_tier_limits_paid_75(self):
        """Paid 75 tier has 75/min, unlimited/day."""
        from av_service import AlphaVantageService
        service = AlphaVantageService(api_key='test-key', tier='paid_75')

        assert service.requests_per_minute == 75
        assert service.requests_per_day is None


class TestAVRequestTracking:
    """Test request tracking functionality."""

    def test_av_get_remaining_requests(self):
        """Verify get_remaining_requests() returns correct info."""
        from av_service import AlphaVantageService
        service = AlphaVantageService(api_key='test-key', tier='free')

        status = service.get_remaining_requests()

        assert status['tier'] == 'free'
        assert status['remaining_this_minute'] == 5
        assert status['remaining_today'] == 25
        assert status['requests_this_minute'] == 0
        assert status['requests_today'] == 0

    @responses.activate
    def test_av_requests_decrease_after_call(self):
        """Verify requests decrease after API call."""
        from av_service import AlphaVantageService
        service = AlphaVantageService(api_key='test-key', tier='paid_30')

        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json={"Global Quote": {"05. price": "100.0"}},
            status=200
        )

        service.get_info("SPY")
        status = service.get_remaining_requests()

        assert status['requests_this_minute'] == 1
        assert status['requests_today'] == 1


class TestAVErrorMessages:
    """Test API error message handling."""

    @responses.activate
    def test_av_error_message_raises(self, av_service):
        """Error Message in response raises exception."""
        responses.add(
            responses.GET,
            "https://www.alphavantage.co/query",
            json={"Error Message": "Invalid API call. Please retry or visit the documentation."},
            status=200
        )

        with pytest.raises(Exception, match="Invalid API call"):
            av_service.get_info("INVALID")
