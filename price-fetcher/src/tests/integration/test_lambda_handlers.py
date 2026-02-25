"""
Integration tests for Lambda handlers.

Tests cover:
- Price fetcher handler (handler)
- Holiday handler (holiday_handler)
- Validator handler (validator_handler)

Issue: #65
"""

import json
import os
import sys
from decimal import Decimal
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

# Add project root, fetchers and src to path for imports
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.insert(0, PROJECT_ROOT)  # For lambda_handler
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'fetchers'))  # For fetchers modules
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))  # For pricedata

from tests.integration.helpers import create_tables, clear_module_caches, add_watchlist_symbol


class MockLambdaContext:
    """Mock AWS Lambda context object."""

    def __init__(self, remaining_time_ms: int = 300000):
        self._remaining_time_ms = remaining_time_ms
        self.function_name = 'test-price-fetcher'
        self.function_version = '$LATEST'
        self.invoked_function_arn = 'arn:aws:lambda:us-west-2:123456789:function:test-price-fetcher'
        self.memory_limit_in_mb = 512
        self.aws_request_id = 'test-request-id'
        self.log_group_name = '/aws/lambda/test-price-fetcher'
        self.log_stream_name = 'test-log-stream'

    def get_remaining_time_in_millis(self) -> int:
        return self._remaining_time_ms


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context with 5 minutes remaining."""
    return MockLambdaContext(remaining_time_ms=300000)


@pytest.fixture
def lambda_context_low_time():
    """Create a mock Lambda context with only 30 seconds remaining."""
    return MockLambdaContext(remaining_time_ms=30000)


@pytest.fixture
def dynamodb_tables(aws_credentials):
    """Create mocked DynamoDB tables for handler testing."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        yield {
            'dynamodb': dynamodb,
            'watchlist_table': watchlist_table,
            'prices_table': prices_table,
        }


# =============================================================================
# Price Fetcher Handler Tests
# =============================================================================

class TestHandlerDryRun:
    """Test dry_run event parameter."""

    def test_handler_dry_run(self, lambda_context):
        """dry_run=true returns immediately without fetching."""
        # Import handler (no need for moto since dry_run skips DB calls)
        from lambda_handler import handler

        event = {'dry_run': True}
        result = handler(event, lambda_context)

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['dry_run'] is True
        assert body['status'] == 'ok'


class TestHandlerEmptyEvent:
    """Test default behavior with empty event."""

    @mock_aws
    def test_handler_empty_event(self, monkeypatch, aws_credentials, lambda_context):
        """Empty event fetches all symbols from watchlist table."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        # Seed with test symbols
        for symbol in ['SPY', 'QQQ']:
            add_watchlist_symbol(watchlist_table, symbol)

        # Mock the PriceDataFetcher to avoid real API calls
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_prices.return_value = {
            'success': ['SPY', 'QQQ'],
            'failed': [],
            'skipped': [],
            'timeout_remaining': [],
            'data': {
                'SPY': [{'etf_symbol': 'SPY', 'current_price': Decimal('605.23')}],
                'QQQ': [{'etf_symbol': 'QQQ', 'current_price': Decimal('520.15')}],
            },
            'timeout_triggered': False,
        }

        # Force reimport lambda_handler
        clear_module_caches()

        with patch('main.PriceDataFetcher', return_value=mock_fetcher):
            from lambda_handler import handler
            result = handler({}, lambda_context)

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['success_count'] == 2
        assert body['failed_count'] == 0


class TestHandlerSpecificSymbols:
    """Test handling of specific symbols in event."""

    @mock_aws
    def test_handler_specific_symbols(self, monkeypatch, aws_credentials, lambda_context):
        """symbols parameter processes only specified symbols."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        # Mock the PriceDataFetcher
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_prices.return_value = {
            'success': ['SPY'],
            'failed': [],
            'skipped': [],
            'timeout_remaining': [],
            'data': {'SPY': [{'etf_symbol': 'SPY', 'current_price': Decimal('605.23')}]},
            'timeout_triggered': False,
        }

        clear_module_caches()

        with patch('main.PriceDataFetcher', return_value=mock_fetcher):
            from lambda_handler import handler
            result = handler({'symbols': ['SPY']}, lambda_context)

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['success_count'] == 1

        # Verify fetch_prices was called with SPY
        call_args = mock_fetcher.fetch_prices.call_args
        assert 'SPY' in call_args.kwargs.get('symbols', call_args.args[0] if call_args.args else [])


class TestHandlerMaxSymbols:
    """Test max_symbols event parameter."""

    @mock_aws
    def test_handler_max_symbols(self, monkeypatch, aws_credentials, lambda_context):
        """max_symbols parameter limits batch size."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        # Seed with 10 symbols
        for i in range(10):
            add_watchlist_symbol(watchlist_table, f'ETF{i}')

        # Mock fetcher to track what symbols it receives
        mock_fetcher = MagicMock()

        def mock_fetch_prices(symbols, context=None, db_service=None):
            return {
                'success': symbols[:2],  # Only process max_symbols
                'failed': [],
                'skipped': [],
                'timeout_remaining': [],
                'data': {s: [{'etf_symbol': s}] for s in symbols[:2]},
                'timeout_triggered': False,
            }

        mock_fetcher.fetch_prices.side_effect = mock_fetch_prices

        clear_module_caches()

        with patch('main.PriceDataFetcher', return_value=mock_fetcher):
            from lambda_handler import handler
            result = handler({'max_symbols': 2}, lambda_context)

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['processed'] == 2


class TestHandlerAllFail:
    """Test handler when all symbols fail."""

    @mock_aws
    def test_handler_all_fail(self, monkeypatch, aws_credentials, lambda_context):
        """All symbols failing returns 207 multi-status."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        for symbol in ['SPY', 'QQQ']:
            add_watchlist_symbol(watchlist_table, symbol)

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_prices.return_value = {
            'success': [],
            'failed': ['SPY', 'QQQ'],
            'skipped': [],
            'timeout_remaining': [],
            'data': {},
            'timeout_triggered': False,
        }

        clear_module_caches()

        with patch('main.PriceDataFetcher', return_value=mock_fetcher):
            from lambda_handler import handler
            result = handler({}, lambda_context)

        assert result['statusCode'] == 207
        body = json.loads(result['body'])
        assert body['failed_count'] == 2
        assert 'SPY' in body['failed_symbols']


class TestHandlerTimeoutPartial:
    """Test handler timeout behavior with partial results."""

    @mock_aws
    def test_handler_timeout_partial(self, monkeypatch, aws_credentials, lambda_context):
        """Timeout mid-batch returns 206 with remaining symbols."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        for symbol in ['SPY', 'QQQ', 'IWM']:
            add_watchlist_symbol(watchlist_table, symbol)

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_prices.return_value = {
            'success': ['SPY'],
            'failed': [],
            'skipped': [],
            'timeout_remaining': ['QQQ', 'IWM'],
            'data': {'SPY': [{'etf_symbol': 'SPY'}]},
            'timeout_triggered': True,
        }

        clear_module_caches()

        with patch('main.PriceDataFetcher', return_value=mock_fetcher):
            from lambda_handler import handler
            result = handler({}, lambda_context)

        assert result['statusCode'] == 206
        body = json.loads(result['body'])
        assert body['timeout_triggered'] is True
        assert body['remaining_count'] == 2
        assert 'QQQ' in body['remaining_symbols']


class TestHandlerNoSymbols:
    """Test handler with empty positions table."""

    @mock_aws
    def test_handler_no_symbols(self, monkeypatch, aws_credentials, lambda_context):
        """Empty watchlist table returns 200 with empty data."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_prices.return_value = {
            'success': [],
            'failed': [],
            'skipped': [],
            'timeout_remaining': [],
            'data': {},
            'timeout_triggered': False,
        }

        clear_module_caches()

        with patch('main.PriceDataFetcher', return_value=mock_fetcher):
            from lambda_handler import handler
            result = handler({}, lambda_context)

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['processed'] == 0


class TestHandlerError:
    """Test handler error handling."""

    def test_handler_exception_returns_500(self, monkeypatch, lambda_context):
        """Unhandled exception returns 500 with error message."""
        clear_module_caches()

        with patch('main.PriceDataFetcher', side_effect=ValueError("Test error")):
            from lambda_handler import handler
            result = handler({}, lambda_context)

        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert body['error'] == 'ValueError'
        assert 'Test error' in body['error_message']


# =============================================================================
# Holiday Handler Tests
# =============================================================================

class TestHolidayHandlerDryRun:
    """Test holiday handler dry_run parameter."""

    def test_holiday_handler_dry_run(self, lambda_context):
        """dry_run=true returns immediately without fetching."""
        from lambda_handler import holiday_handler

        event = {'dry_run': True}
        result = holiday_handler(event, lambda_context)

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['dry_run'] is True
        assert body['status'] == 'ok'


class TestHolidayHandlerDefault:
    """Test holiday handler default behavior."""

    def test_holiday_handler_default(self, monkeypatch, lambda_context):
        """Default exchange is US, fetches from Finnhub."""
        # Clear all relevant modules first
        for mod_name in list(sys.modules.keys()):
            if any(x in mod_name for x in ['lambda_handler', 'holiday_fetcher', 'core.holiday_fetcher']):
                del sys.modules[mod_name]

        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.fetch.return_value = {
            'success': True,
            'exchange': 'US',
            'api_count': 10,
            'detected_count': 0,
            'total_count': 10,
        }

        # Patch at module level before import
        import core.holiday_fetcher as hf_module
        original_class = hf_module.HolidayFetcher

        try:
            hf_module.HolidayFetcher = MagicMock(return_value=mock_fetcher_instance)

            # Now import lambda_handler fresh
            import lambda_handler as lh
            result = lh.holiday_handler({}, lambda_context)

            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert body['exchange'] == 'US'

            # Verify fetch was called
            mock_fetcher_instance.fetch.assert_called_once()
        finally:
            hf_module.HolidayFetcher = original_class


class TestHolidayHandlerExchange:
    """Test holiday handler with exchange parameter."""

    def test_holiday_handler_exchange(self, monkeypatch, lambda_context):
        """Custom exchange parameter is passed to fetcher."""
        for mod_name in list(sys.modules.keys()):
            if any(x in mod_name for x in ['lambda_handler', 'holiday_fetcher', 'core.holiday_fetcher']):
                del sys.modules[mod_name]

        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.fetch.return_value = {
            'success': True,
            'exchange': 'LSE',
            'api_count': 5,
            'detected_count': 0,
            'total_count': 5,
        }

        import core.holiday_fetcher as hf_module
        original_class = hf_module.HolidayFetcher

        try:
            hf_module.HolidayFetcher = MagicMock(return_value=mock_fetcher_instance)

            import lambda_handler as lh
            result = lh.holiday_handler({'exchange': 'LSE'}, lambda_context)

            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert body['exchange'] == 'LSE'

            # Verify fetch was called with LSE exchange
            mock_fetcher_instance.fetch.assert_called_once()
            call_kwargs = mock_fetcher_instance.fetch.call_args.kwargs
            assert call_kwargs.get('exchange') == 'LSE'
        finally:
            hf_module.HolidayFetcher = original_class


class TestHolidayHandlerApiFail:
    """Test holiday handler when API fails."""

    def test_holiday_handler_api_fail(self, monkeypatch, lambda_context):
        """Finnhub API error returns 500."""
        for mod_name in list(sys.modules.keys()):
            if any(x in mod_name for x in ['lambda_handler', 'holiday_fetcher', 'core.holiday_fetcher']):
                del sys.modules[mod_name]

        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.fetch.return_value = {
            'success': False,
            'exchange': 'US',
            'api_count': 0,
            'error': 'API unavailable',
        }

        import core.holiday_fetcher as hf_module
        original_class = hf_module.HolidayFetcher

        try:
            hf_module.HolidayFetcher = MagicMock(return_value=mock_fetcher_instance)

            import lambda_handler as lh
            result = lh.holiday_handler({}, lambda_context)

            assert result['statusCode'] == 500
        finally:
            hf_module.HolidayFetcher = original_class


# =============================================================================
# Validator Handler Tests
# =============================================================================

class TestValidatorHandlerDryRun:
    """Test validator handler dry_run parameter."""

    def test_validator_handler_dry_run(self, lambda_context):
        """dry_run=true returns immediately without validating."""
        from lambda_handler import validator_handler

        event = {'dry_run': True}
        result = validator_handler(event, lambda_context)

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['dry_run'] is True
        assert body['status'] == 'ok'


class TestValidatorHandlerDailyComplete:
    """Test validator with complete daily data."""

    @mock_aws
    def test_validator_daily_complete(self, monkeypatch, aws_credentials, lambda_context):
        """All symbols complete returns 200."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        for symbol in ['SPY', 'QQQ']:
            add_watchlist_symbol(watchlist_table, symbol)

        # Clear modules before patching
        clear_module_caches(['validator', 'core.validator'])

        mock_validator_instance = MagicMock()
        mock_validator_instance.validate_symbols.return_value = {
            'complete': ['SPY', 'QQQ'],
            'incomplete': [],
            'total': 2,
            'complete_count': 2,
            'incomplete_count': 0,
            'interval': 'daily',
        }

        import core.validator as validator_module
        original_class = validator_module.PriceValidator

        try:
            validator_module.PriceValidator = MagicMock(return_value=mock_validator_instance)

            import lambda_handler as lh
            result = lh.validator_handler({}, lambda_context)

            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert body['complete_count'] == 2
            assert body['incomplete_count'] == 0
        finally:
            validator_module.PriceValidator = original_class


class TestValidatorHandlerDailyIncomplete:
    """Test validator with incomplete daily data."""

    @mock_aws
    def test_validator_daily_incomplete(self, monkeypatch, aws_credentials, lambda_context):
        """Missing dates returns 207 multi-status."""
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        watchlist_table, prices_table = create_tables(dynamodb)

        for symbol in ['SPY', 'QQQ']:
            add_watchlist_symbol(watchlist_table, symbol)

        # Clear modules before patching
        clear_module_caches(['validator', 'core.validator'])

        mock_validator_instance = MagicMock()
        mock_validator_instance.validate_symbols.return_value = {
            'complete': ['SPY'],
            'incomplete': [{
                'symbol': 'QQQ',
                'missing_count': 3,
                'first_missing': '2026-01-28',
                'last_missing': '2026-01-30',
            }],
            'total': 2,
            'complete_count': 1,
            'incomplete_count': 1,
            'interval': 'daily',
        }

        import core.validator as validator_module
        original_class = validator_module.PriceValidator

        try:
            validator_module.PriceValidator = MagicMock(return_value=mock_validator_instance)

            import lambda_handler as lh
            result = lh.validator_handler({}, lambda_context)

            assert result['statusCode'] == 207
            body = json.loads(result['body'])
            assert body['complete_count'] == 1
            assert body['incomplete_count'] == 1
        finally:
            validator_module.PriceValidator = original_class
