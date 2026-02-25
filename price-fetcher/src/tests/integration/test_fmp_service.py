"""
Integration tests for Financial Modeling Prep (FMP) service.

Tests cover:
- get_info success and failure cases
- get_historical_data with different intervals
- Tier-specific rate limits
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
def fmp_service():
    """Create FMPService with test API key."""
    from fmp_service import FMPService
    return FMPService(api_key='test-api-key-12345', tier='starter')


@pytest.fixture
def fmp_quote_response():
    """Sample successful quote response (returns list)."""
    return [
        {
            "symbol": "SPY",
            "name": "SPDR S&P 500 ETF Trust",
            "price": 605.23,
            "changePercentage": 0.3699,
            "change": 2.23,
            "dayLow": 602.10,
            "dayHigh": 607.50,
            "yearHigh": 610.00,
            "yearLow": 480.00,
            "marketCap": None,
            "priceAvg50": 590.00,
            "priceAvg200": 560.00,
            "volume": 45000000,
            "avgVolume": 50000000,
            "exchange": "NYSE",
            "open": 603.00,
            "previousClose": 603.00,
            "eps": None,
            "pe": None,
            "earningsAnnouncement": None,
            "sharesOutstanding": None,
            "timestamp": 1738267200
        }
    ]


@pytest.fixture
def fmp_historical_response():
    """Sample historical-price-eod/full response."""
    return {
        "symbol": "SPY",
        "historical": [
            {"date": "2026-01-30", "open": 603.00, "high": 607.50, "low": 602.10, "close": 605.23, "volume": 45000000},
            {"date": "2026-01-29", "open": 600.00, "high": 603.50, "low": 599.00, "close": 602.15, "volume": 42000000},
            {"date": "2026-01-28", "open": 598.00, "high": 601.00, "low": 597.00, "close": 600.50, "volume": 38000000},
        ]
    }


# =============================================================================
# Quote Tests
# =============================================================================

class TestFMPGetInfoSuccess:
    """Test successful quote fetching."""

    @responses.activate
    def test_fmp_get_info_success(self, fmp_service, fmp_quote_response):
        """/quote returns list, extract first item."""
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/quote",
            json=fmp_quote_response,
            status=200
        )

        result = fmp_service.get_info("SPY")

        assert result is not None
        assert result['regularMarketPrice'] == 605.23
        assert result['volume'] == 45000000
        assert result['regularMarketOpen'] == 603.0
        assert result['regularMarketDayHigh'] == 607.5
        assert result['regularMarketDayLow'] == 602.1
        assert result['regularMarketPreviousClose'] == 603.0
        assert abs(result['regularMarketChangePercent'] - 0.3699) < 0.001
        assert result['symbol'] == 'SPY'


class TestFMPGetInfoEmptyList:
    """Test handling of empty response array."""

    @responses.activate
    def test_fmp_get_info_empty_list(self, fmp_service):
        """Handle empty response array."""
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/quote",
            json=[],
            status=200
        )

        result = fmp_service.get_info("INVALID123")

        assert result is None


class TestFMPGetInfoZeroPrice:
    """Test handling of zero price."""

    @responses.activate
    def test_fmp_get_info_zero_price(self, fmp_service):
        """Zero price returns None."""
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/quote",
            json=[{"symbol": "INVALID", "price": 0}],
            status=200
        )

        result = fmp_service.get_info("INVALID")

        assert result is None


class TestFMPGetInfo402:
    """Test handling of 402 payment required."""

    @responses.activate
    def test_fmp_get_info_payment_required(self, fmp_service):
        """402 response returns None without retry."""
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/quote",
            status=402
        )

        result = fmp_service.get_info("PREMIUM_ONLY")

        assert result is None
        assert len(responses.calls) == 1


# =============================================================================
# Historical Data Tests
# =============================================================================

class TestFMPGetHistoricalDaily:
    """Test daily historical data."""

    @responses.activate
    def test_fmp_get_historical_daily(self, fmp_service, fmp_historical_response):
        """/historical-price-eod/full with date filtering."""
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/historical-price-eod/full",
            json=fmp_historical_response,
            status=200
        )

        result = fmp_service.get_historical_data("SPY", period="1mo", interval="1d")

        assert result is not None
        assert len(result) == 3

        # Results in chronological order (oldest first after reverse)
        assert result[0]['date'] == '2026-01-28'
        assert result[0]['close'] == 600.50
        assert result[2]['date'] == '2026-01-30'
        assert result[2]['close'] == 605.23


class TestFMPGetHistoricalIntraday:
    """Test intraday historical data."""

    @responses.activate
    def test_fmp_get_historical_intraday(self, fmp_service):
        """/historical-chart/{interval} endpoint."""
        now = datetime.now()
        intraday_response = [
            {"date": f"{now.strftime('%Y-%m-%d')} 15:45:00", "close": 605.50},
            {"date": f"{now.strftime('%Y-%m-%d')} 15:30:00", "close": 605.25},
            {"date": f"{now.strftime('%Y-%m-%d')} 15:15:00", "close": 605.00},
        ]

        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/historical-chart/15min",
            json=intraday_response,
            status=200
        )

        result = fmp_service.get_historical_data("SPY", period="1d", interval="15m")

        assert result is not None
        assert len(result) == 3

        # Verify endpoint was correct
        assert "historical-chart/15min" in responses.calls[0].request.url


class TestFMPGetHistorical5Min:
    """Test 5-minute historical data."""

    @responses.activate
    def test_fmp_get_historical_5min(self, fmp_service):
        """/historical-chart/5min endpoint."""
        now = datetime.now()
        intraday_response = [
            {"date": f"{now.strftime('%Y-%m-%d')} 09:35:00", "close": 603.10},
            {"date": f"{now.strftime('%Y-%m-%d')} 09:30:00", "close": 603.00},
        ]

        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/historical-chart/5min",
            json=intraday_response,
            status=200
        )

        result = fmp_service.get_historical_data("SPY", period="1d", interval="5m")

        assert result is not None
        assert "historical-chart/5min" in responses.calls[0].request.url


class TestFMPGetHistoricalEmpty:
    """Test empty historical data."""

    @responses.activate
    def test_fmp_get_historical_empty(self, fmp_service):
        """Empty historical returns None."""
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/historical-price-eod/full",
            json={"symbol": "INVALID", "historical": []},
            status=200
        )

        result = fmp_service.get_historical_data("INVALID", period="1mo", interval="1d")

        assert result is None


# =============================================================================
# Rate Limit and Tier Tests
# =============================================================================

class TestFMPTierLimits:
    """Test tier-specific rate limits."""

    def test_fmp_tier_limits_free(self):
        """Free tier has 250/day, no per-minute limit."""
        from fmp_service import FMPService
        service = FMPService(api_key='test-key', tier='free')

        assert service.calls_per_day == 250
        assert service.calls_per_minute is None

    def test_fmp_tier_limits_starter(self):
        """Starter tier has 300/min, unlimited/day."""
        from fmp_service import FMPService
        service = FMPService(api_key='test-key', tier='starter')

        assert service.calls_per_minute == 300
        assert service.calls_per_day is None

    def test_fmp_tier_limits_premium(self):
        """Premium tier has 750/min, unlimited/day."""
        from fmp_service import FMPService
        service = FMPService(api_key='test-key', tier='premium')

        assert service.calls_per_minute == 750
        assert service.calls_per_day is None

    def test_fmp_tier_limits_ultimate(self):
        """Ultimate tier has 3000/min, unlimited/day."""
        from fmp_service import FMPService
        service = FMPService(api_key='test-key', tier='ultimate')

        assert service.calls_per_minute == 3000
        assert service.calls_per_day is None


class TestFMPRateLimitRetry:
    """Test rate limit handling."""

    @responses.activate
    def test_fmp_rate_limit_retry(self, fmp_service, fmp_quote_response):
        """429 response triggers retry with backoff."""
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/quote",
            status=429
        )
        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/quote",
            json=fmp_quote_response,
            status=200
        )

        with patch('fmp_service.time.sleep'):
            result = fmp_service.get_info("SPY")

        assert result is not None
        assert len(responses.calls) == 2


class TestFMPRequestTracking:
    """Test request tracking functionality."""

    def test_fmp_get_remaining_requests_free(self):
        """Verify get_remaining_requests() for free tier."""
        from fmp_service import FMPService
        service = FMPService(api_key='test-key', tier='free')

        status = service.get_remaining_requests()

        assert status['tier'] == 'free'
        assert status['remaining_today'] == 250
        assert status['requests_today'] == 0
        # Free tier doesn't have per-minute tracking
        assert 'remaining_this_minute' not in status

    def test_fmp_get_remaining_requests_paid(self):
        """Verify get_remaining_requests() for paid tier."""
        from fmp_service import FMPService
        service = FMPService(api_key='test-key', tier='starter')

        status = service.get_remaining_requests()

        assert status['tier'] == 'starter'
        assert status['remaining_today'] == 'unlimited'
        assert status['remaining_this_minute'] == 300

    @responses.activate
    def test_fmp_requests_decrease_after_call(self):
        """Verify requests decrease after API call."""
        from fmp_service import FMPService
        service = FMPService(api_key='test-key', tier='free')

        responses.add(
            responses.GET,
            "https://financialmodelingprep.com/stable/quote",
            json=[{"symbol": "SPY", "price": 100.0}],
            status=200
        )

        service.get_info("SPY")
        status = service.get_remaining_requests()

        assert status['requests_today'] == 1
        assert status['remaining_today'] == 249
