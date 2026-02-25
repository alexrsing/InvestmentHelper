"""
Integration tests for the data source fallback chain in PriceDataFetcher.

Tests verify that when one data source fails or returns invalid data,
the fetcher correctly falls back to the next source in the chain.

Fallback order (auto mode, Lambda - no yfinance):
1. Twelve Data
2. Alpha Vantage
3. Finnhub
4. Financial Modeling Prep

Issue: #67
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add fetchers to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'fetchers'))


class TestFallbackTDFailsUsesAV:
    """Test fallback from Twelve Data to Alpha Vantage."""

    def test_fallback_td_fails_uses_av(self, monkeypatch):
        """Twelve Data returns None, Alpha Vantage succeeds."""
        # Mock API keys
        monkeypatch.setenv('TWELVEDATA_API_KEY', 'test-td-key')
        monkeypatch.setenv('ALPHA_VANTAGE_API_KEY', 'test-av-key')
        monkeypatch.setenv('DATA_SOURCE', 'auto')

        # Mock the service classes
        with patch('main.TwelveDataService') as mock_td_class, \
             patch('main.AlphaVantageService') as mock_av_class, \
             patch('main.FinnhubService') as mock_fh_class, \
             patch('main.FMPService') as mock_fmp_class, \
             patch('main.YFINANCE_AVAILABLE', False):

            # TD returns None (failure)
            mock_td_instance = MagicMock()
            mock_td_instance.get_info.return_value = None
            mock_td_class.return_value = mock_td_instance

            # AV returns valid data
            mock_av_instance = MagicMock()
            mock_av_instance.get_info.return_value = {
                'regularMarketPrice': 605.23,
                'volume': 45000000,
                'regularMarketChangePercent': 0.45,
            }
            mock_av_class.return_value = mock_av_instance

            # FH and FMP should not be called
            mock_fh_class.return_value = MagicMock()
            mock_fmp_class.return_value = MagicMock()

            # Import after mocking
            from main import PriceDataFetcher

            fetcher = PriceDataFetcher(data_source='auto')
            data, source = fetcher.get_info('SPY')

            # Should have used Alpha Vantage
            assert source == 'alphavantage'
            assert data['regularMarketPrice'] == 605.23

            # TD was called and failed
            mock_td_instance.get_info.assert_called_once_with('SPY')

            # AV was called and succeeded
            mock_av_instance.get_info.assert_called_once_with('SPY')


class TestFallbackAllFail:
    """Test behavior when all sources fail."""

    def test_fallback_all_fail(self, monkeypatch):
        """All sources fail, returns (None, 'none')."""
        # Mock API keys for all services
        monkeypatch.setenv('TWELVEDATA_API_KEY', 'test-td-key')
        monkeypatch.setenv('ALPHA_VANTAGE_API_KEY', 'test-av-key')
        monkeypatch.setenv('FINNHUB_API_KEY', 'test-fh-key')
        monkeypatch.setenv('FMP_API_KEY', 'test-fmp-key')
        monkeypatch.setenv('DATA_SOURCE', 'auto')

        with patch('main.TwelveDataService') as mock_td_class, \
             patch('main.AlphaVantageService') as mock_av_class, \
             patch('main.FinnhubService') as mock_fh_class, \
             patch('main.FMPService') as mock_fmp_class, \
             patch('main.YFINANCE_AVAILABLE', False):

            # All services return None
            for mock_class in [mock_td_class, mock_av_class, mock_fh_class, mock_fmp_class]:
                mock_instance = MagicMock()
                mock_instance.get_info.return_value = None
                mock_class.return_value = mock_instance

            from main import PriceDataFetcher

            fetcher = PriceDataFetcher(data_source='auto')
            data, source = fetcher.get_info('INVALID_SYMBOL')

            assert data is None
            assert source == 'none'


class TestFallbackFirstSuccessStops:
    """Test that fallback stops after first successful source."""

    def test_fallback_first_success_stops(self, monkeypatch):
        """TD succeeds, doesn't call AV/FH/FMP."""
        monkeypatch.setenv('TWELVEDATA_API_KEY', 'test-td-key')
        monkeypatch.setenv('ALPHA_VANTAGE_API_KEY', 'test-av-key')
        monkeypatch.setenv('FINNHUB_API_KEY', 'test-fh-key')
        monkeypatch.setenv('FMP_API_KEY', 'test-fmp-key')
        monkeypatch.setenv('DATA_SOURCE', 'auto')

        with patch('main.TwelveDataService') as mock_td_class, \
             patch('main.AlphaVantageService') as mock_av_class, \
             patch('main.FinnhubService') as mock_fh_class, \
             patch('main.FMPService') as mock_fmp_class, \
             patch('main.YFINANCE_AVAILABLE', False):

            # TD returns valid data immediately
            mock_td_instance = MagicMock()
            mock_td_instance.get_info.return_value = {
                'regularMarketPrice': 605.23,
                'volume': 45000000,
                'regularMarketChangePercent': 0.45,
            }
            mock_td_class.return_value = mock_td_instance

            # Create mock instances for other services
            mock_av_instance = MagicMock()
            mock_av_class.return_value = mock_av_instance

            mock_fh_instance = MagicMock()
            mock_fh_class.return_value = mock_fh_instance

            mock_fmp_instance = MagicMock()
            mock_fmp_class.return_value = mock_fmp_instance

            from main import PriceDataFetcher

            fetcher = PriceDataFetcher(data_source='auto')
            data, source = fetcher.get_info('SPY')

            # Should have used Twelve Data
            assert source == 'twelvedata'
            assert data['regularMarketPrice'] == 605.23

            # TD was called
            mock_td_instance.get_info.assert_called_once_with('SPY')

            # Others were NOT called
            mock_av_instance.get_info.assert_not_called()
            mock_fh_instance.get_info.assert_not_called()
            mock_fmp_instance.get_info.assert_not_called()


class TestFallbackOrderCorrect:
    """Test that fallback order is TD -> AV -> FH -> FMP."""

    def test_fallback_order_correct(self, monkeypatch):
        """Verify order: TD -> AV -> FH -> FMP (no yfinance in Lambda)."""
        monkeypatch.setenv('TWELVEDATA_API_KEY', 'test-td-key')
        monkeypatch.setenv('ALPHA_VANTAGE_API_KEY', 'test-av-key')
        monkeypatch.setenv('FINNHUB_API_KEY', 'test-fh-key')
        monkeypatch.setenv('FMP_API_KEY', 'test-fmp-key')
        monkeypatch.setenv('DATA_SOURCE', 'auto')

        call_order = []

        with patch('main.TwelveDataService') as mock_td_class, \
             patch('main.AlphaVantageService') as mock_av_class, \
             patch('main.FinnhubService') as mock_fh_class, \
             patch('main.FMPService') as mock_fmp_class, \
             patch('main.YFINANCE_AVAILABLE', False):

            # Create mock instances that track call order
            def make_mock(name, should_succeed=False):
                mock_instance = MagicMock()

                def get_info_side_effect(symbol):
                    call_order.append(name)
                    if should_succeed:
                        return {
                            'regularMarketPrice': 100.0,
                            'volume': 1000,
                            'regularMarketChangePercent': 0.1,
                        }
                    return None

                mock_instance.get_info.side_effect = get_info_side_effect
                return mock_instance

            # All fail except FMP (last one)
            mock_td_class.return_value = make_mock('TD', should_succeed=False)
            mock_av_class.return_value = make_mock('AV', should_succeed=False)
            mock_fh_class.return_value = make_mock('FH', should_succeed=False)
            mock_fmp_class.return_value = make_mock('FMP', should_succeed=True)

            from main import PriceDataFetcher

            fetcher = PriceDataFetcher(data_source='auto')
            data, source = fetcher.get_info('SPY')

            # Should have succeeded with FMP
            assert source == 'fmp'

            # Verify call order
            assert call_order == ['TD', 'AV', 'FH', 'FMP'], f"Expected order TD->AV->FH->FMP, got {call_order}"


class TestYFinanceSkippedInLambda:
    """Test that yfinance is skipped when not available."""

    def test_yfinance_skipped_when_unavailable(self, monkeypatch):
        """yfinance not called when YFINANCE_AVAILABLE is False."""
        monkeypatch.setenv('TWELVEDATA_API_KEY', 'test-td-key')
        monkeypatch.setenv('DATA_SOURCE', 'auto')

        with patch('main.TwelveDataService') as mock_td_class, \
             patch('main.YFINANCE_AVAILABLE', False), \
             patch('main.YahooFinanceService') as mock_yf_class:

            mock_td_instance = MagicMock()
            mock_td_instance.get_info.return_value = {
                'regularMarketPrice': 605.23,
                'volume': 45000000,
                'regularMarketChangePercent': 0.45,
            }
            mock_td_class.return_value = mock_td_instance

            from main import PriceDataFetcher

            fetcher = PriceDataFetcher(data_source='auto')

            # yfinance service should not be initialized
            assert fetcher.yf_service is None

            data, source = fetcher.get_info('SPY')

            # Should have used TD, not yfinance
            assert source == 'twelvedata'

            # YahooFinanceService should never have been instantiated
            mock_yf_class.assert_not_called()
