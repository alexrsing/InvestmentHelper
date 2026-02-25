"""
Integration tests for Twelve Data service.

Tests cover:
- get_info success and failure cases
- get_historical_data with different intervals
- Rate limiting and retry behavior
- Credit tracking

Issue: #64
"""

import json
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import responses
from responses import matchers

# Add fetchers to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'fetchers'))


@pytest.fixture
def td_service():
    """Create TwelveDataService with test API key."""
    # Import here so path is set
    from td_service import TwelveDataService
    return TwelveDataService(api_key='test-api-key-12345', tier='grow')


@pytest.fixture
def td_quote_response():
    """Sample successful quote response."""
    return {
        "symbol": "SPY",
        "name": "SPDR S&P 500 ETF Trust",
        "exchange": "NYSE",
        "currency": "USD",
        "datetime": "2026-01-30",
        "open": "603.00",
        "high": "607.50",
        "low": "602.10",
        "close": "605.23",
        "volume": "45000000",
        "previous_close": "603.00"
    }


@pytest.fixture
def td_time_series_response():
    """Sample successful time series response."""
    return {
        "meta": {
            "symbol": "SPY",
            "interval": "1day",
            "currency": "USD"
        },
        "values": [
            {"datetime": "2026-01-30", "open": "603.00", "high": "607.50", "low": "602.10", "close": "605.23", "volume": "45000000"},
            {"datetime": "2026-01-29", "open": "600.00", "high": "603.50", "low": "599.00", "close": "602.15", "volume": "42000000"},
            {"datetime": "2026-01-28", "open": "598.00", "high": "601.00", "low": "597.00", "close": "600.50", "volume": "38000000"},
        ],
        "status": "ok"
    }


# =============================================================================
# Quote Tests
# =============================================================================

class TestTDGetInfoSuccess:
    """Test successful quote fetching."""

    @responses.activate
    def test_td_get_info_success(self, td_service, td_quote_response):
        """Fetch quote, verify normalized fields."""
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/quote",
            json=td_quote_response,
            status=200
        )

        result = td_service.get_info("SPY")

        assert result is not None
        assert result['regularMarketPrice'] == 605.23
        assert result['volume'] == 45000000
        assert result['regularMarketOpen'] == 603.0
        assert result['regularMarketDayHigh'] == 607.5
        assert result['regularMarketDayLow'] == 602.1
        assert result['regularMarketPreviousClose'] == 603.0
        # Verify change percent calculation: (605.23 - 603.00) / 603.00 * 100 = 0.37%
        assert abs(result['regularMarketChangePercent'] - 0.37) < 0.01


class TestTDGetInfoInvalidSymbol:
    """Test handling of invalid symbols."""

    @responses.activate
    def test_td_get_info_invalid_symbol(self, td_service):
        """Handle unknown symbol by raising exception."""
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/quote",
            json={"status": "error", "message": "Symbol not found"},
            status=200
        )

        # The service raises an exception for API errors like "Symbol not found"
        with pytest.raises(Exception, match="Symbol not found"):
            td_service.get_info("INVALID123")


class TestTDGetInfo403:
    """Test handling of 403 forbidden response."""

    @responses.activate
    def test_td_get_info_forbidden(self, td_service):
        """Handle 403 (symbol not available) without retry."""
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/quote",
            status=403
        )

        result = td_service.get_info("RESTRICTED")

        assert result is None
        # Should only be 1 request (no retries on 403)
        assert len(responses.calls) == 1


# =============================================================================
# Historical Data Tests
# =============================================================================

class TestTDGetHistoricalDaily:
    """Test daily historical data fetching."""

    @responses.activate
    def test_td_get_historical_daily(self, td_service, td_time_series_response):
        """Fetch 1mo daily data, verify date/close format."""
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/time_series",
            json=td_time_series_response,
            status=200
        )

        result = td_service.get_historical_data("SPY", period="1mo", interval="1d")

        assert result is not None
        assert len(result) == 3

        # Results should be in chronological order (oldest first)
        assert result[0]['date'] == '2026-01-28'
        assert result[0]['close'] == 600.50
        assert result[1]['date'] == '2026-01-29'
        assert result[2]['date'] == '2026-01-30'
        assert result[2]['close'] == 605.23


class TestTDGetHistoricalIntraday:
    """Test intraday historical data fetching."""

    @responses.activate
    def test_td_get_historical_intraday(self, td_service):
        """Fetch 15m/5m intervals, verify outputsize logic."""
        intraday_response = {
            "meta": {"symbol": "SPY", "interval": "15min"},
            "values": [
                {"datetime": "2026-01-30 15:45:00", "close": "605.50"},
                {"datetime": "2026-01-30 15:30:00", "close": "605.25"},
                {"datetime": "2026-01-30 15:15:00", "close": "605.00"},
            ],
            "status": "ok"
        }

        responses.add(
            responses.GET,
            "https://api.twelvedata.com/time_series",
            json=intraday_response,
            status=200
        )

        result = td_service.get_historical_data("SPY", period="5d", interval="15m")

        assert result is not None
        assert len(result) == 3

        # Verify outputsize was passed correctly
        request = responses.calls[0].request
        assert "outputsize=130" in request.url  # 5 days * 26 intervals

        # Results in chronological order
        assert result[0]['date'] == '2026-01-30 15:15:00'
        assert result[2]['date'] == '2026-01-30 15:45:00'


class TestTDGetHistorical5Min:
    """Test 5-minute interval data."""

    @responses.activate
    def test_td_get_historical_5min(self, td_service):
        """Fetch 5m intervals for 1 day."""
        response = {
            "meta": {"symbol": "SPY", "interval": "5min"},
            "values": [
                {"datetime": "2026-01-30 09:35:00", "close": "603.10"},
                {"datetime": "2026-01-30 09:30:00", "close": "603.00"},
            ],
            "status": "ok"
        }

        responses.add(
            responses.GET,
            "https://api.twelvedata.com/time_series",
            json=response,
            status=200
        )

        result = td_service.get_historical_data("SPY", period="1d", interval="5m")

        assert result is not None
        # Verify outputsize for 1d/5min
        request = responses.calls[0].request
        assert "outputsize=78" in request.url


# =============================================================================
# Rate Limiting Tests
# =============================================================================

class TestTDRateLimitRetry:
    """Test exponential backoff on 429 response."""

    @responses.activate
    def test_td_rate_limit_retry(self, td_service, td_quote_response):
        """Verify exponential backoff on 429 response."""
        # First request returns 429, second succeeds
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/quote",
            status=429
        )
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/quote",
            json=td_quote_response,
            status=200
        )

        # Patch time.sleep to avoid actual waiting
        with patch('td_service.time.sleep'):
            result = td_service.get_info("SPY")

        assert result is not None
        assert result['regularMarketPrice'] == 605.23
        assert len(responses.calls) == 2


class TestTDRateLimitMessage:
    """Test rate limit in response body."""

    @responses.activate
    def test_td_api_credit_error_retry(self, td_service, td_quote_response):
        """Verify retry on API credits error message."""
        # First request returns credit error
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/quote",
            json={"status": "error", "message": "API credits exhausted"},
            status=200
        )
        # Second succeeds
        responses.add(
            responses.GET,
            "https://api.twelvedata.com/quote",
            json=td_quote_response,
            status=200
        )

        with patch('td_service.time.sleep'):
            result = td_service.get_info("SPY")

        assert result is not None
        assert len(responses.calls) == 2


# =============================================================================
# Credit Tracking Tests
# =============================================================================

class TestTDCreditTracking:
    """Test credit tracking functionality."""

    def test_td_get_remaining_credits(self):
        """Verify get_remaining_credits() returns correct info."""
        from td_service import TwelveDataService
        service = TwelveDataService(api_key='test-key', tier='free')

        credits = service.get_remaining_credits()

        assert credits['tier'] == 'free'
        assert credits['remaining_this_minute'] == 8  # Free tier = 8/min
        assert credits['remaining_today'] == 800  # Free tier = 800/day
        assert credits['credits_this_minute'] == 0
        assert credits['credits_today'] == 0

    @responses.activate
    def test_td_credits_decrease_after_request(self):
        """Verify credits decrease after API call."""
        from td_service import TwelveDataService
        service = TwelveDataService(api_key='test-key', tier='grow')

        responses.add(
            responses.GET,
            "https://api.twelvedata.com/quote",
            json={"close": "100.0", "previous_close": "99.0", "volume": "1000"},
            status=200
        )

        # Make a request
        service.get_info("SPY")

        credits = service.get_remaining_credits()
        assert credits['credits_this_minute'] == 1
        assert credits['credits_today'] == 1


class TestTDTierLimits:
    """Test different tier rate limits."""

    def test_td_tier_limits_free(self):
        """Free tier has 8/min, 800/day."""
        from td_service import TwelveDataService
        service = TwelveDataService(api_key='test-key', tier='free')

        assert service.credits_per_minute == 8
        assert service.credits_per_day == 800

    def test_td_tier_limits_grow(self):
        """Grow tier has 800/min, unlimited/day."""
        from td_service import TwelveDataService
        service = TwelveDataService(api_key='test-key', tier='grow')

        assert service.credits_per_minute == 800
        assert service.credits_per_day is None

    def test_td_tier_limits_pro(self):
        """Pro tier has 4000/min, unlimited/day."""
        from td_service import TwelveDataService
        service = TwelveDataService(api_key='test-key', tier='pro')

        assert service.credits_per_minute == 4000
        assert service.credits_per_day is None
