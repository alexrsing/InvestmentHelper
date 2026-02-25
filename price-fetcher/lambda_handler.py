"""
AWS Lambda handler entry points for price-fetcher.

This module provides Lambda-compatible handlers that wrap the existing
fetcher functionality for serverless execution.

Handlers:
- handler: Main price fetcher (EventBridge or manual invocation)
- holiday_handler: Market holiday calendar updates
- validator_handler: Price data completeness validation
"""

import json
import os
import sys
from datetime import date
from typing import Any, Dict, List, Optional

# Add fetchers directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fetchers'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Setup logging - must be done before importing other modules
from logging_config import setup_logging, get_logger

# Initialize logging for Lambda (JSON format for CloudWatch Insights)
setup_logging(json_format=True)
logger = get_logger(__name__)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main price fetcher Lambda handler.

    Can be triggered by:
    - EventBridge scheduled event
    - Manual invocation with optional parameters

    Event parameters (optional):
    - symbols: list[str] - Specific symbols to fetch (default: all tracked)
    - force_refresh: bool - Ignore staleness threshold
    - max_symbols: int - Limit symbols per run
    - dry_run: bool - Return without fetching (for smoke tests)

    Returns:
        Dict with statusCode and body containing fetch results:
        - 200: All symbols processed successfully
        - 206: Partial content (timeout caused early exit)
        - 207: Multi-status (some symbols failed)
        - 500: Handler error
    """
    logger.info("Price fetcher invoked", extra={'event_keys': list(event.keys())})

    # Handle dry run for smoke tests
    if event.get('dry_run'):
        logger.info("Dry run requested, returning success")
        return {
            'statusCode': 200,
            'body': json.dumps({'dry_run': True, 'status': 'ok'})
        }

    try:
        # Import fetcher (api_keys module handles Secrets Manager loading)
        from main import PriceDataFetcher
        from db_service import DBService
        from batch import get_symbols_for_run

        # Extract parameters from event
        symbols = event.get('symbols')
        force_refresh = event.get('force_refresh', False)
        max_symbols = event.get('max_symbols')

        # Override max symbols from environment if not in event
        if max_symbols is None:
            max_symbols_env = os.getenv('MAX_SYMBOLS_PER_RUN', '').strip()
            max_symbols = int(max_symbols_env) if max_symbols_env else 50

        logger.info(
            "Starting fetch",
            extra={
                'symbols_provided': symbols is not None,
                'force_refresh': force_refresh,
                'max_symbols': max_symbols
            }
        )

        # Initialize services
        db = DBService()
        fetcher = PriceDataFetcher()

        # Get symbols to process from watchlist
        if symbols is None:
            all_symbols = db.get_watchlist_symbols(enabled_only=True)
            symbols = get_symbols_for_run(all_symbols, max_symbols)
        else:
            symbols = get_symbols_for_run(symbols, max_symbols)

        logger.info("Processing symbols", extra={'count': len(symbols)})

        # Use timeout-aware fetch_prices method
        # Pass context for accurate Lambda timeout tracking
        result = fetcher.fetch_prices(
            symbols=symbols,
            context=context,
            db_service=db
        )

        # Determine status code based on results
        if result.get('timeout_triggered'):
            status_code = 206  # Partial content
        elif result['failed']:
            status_code = 207  # Multi-status
        else:
            status_code = 200

        response_body = {
            'processed': len(result['success']) + len(result['failed']) + len(result['skipped']),
            'success_count': len(result['success']),
            'failed_count': len(result['failed']),
            'skipped_count': len(result['skipped']),
            'remaining_count': len(result.get('timeout_remaining', [])),
            'timeout_triggered': result.get('timeout_triggered', False),
            'failed_symbols': result['failed'][:10],  # Limit to first 10
            'remaining_symbols': result.get('timeout_remaining', [])[:10],  # Limit to first 10
        }

        logger.info("Fetch complete", extra=response_body)

        return {
            'statusCode': status_code,
            'body': json.dumps(response_body)
        }

    except Exception as e:
        logger.error(
            "Price fetch failed",
            extra={'error': type(e).__name__, 'error_message': str(e)},
            exc_info=True
        )
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': type(e).__name__,
                'error_message': str(e)
            })
        }


def holiday_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Market holiday fetcher Lambda handler.

    Updates the market holiday calendar from external sources.
    Typically run weekly on Sunday.

    Event parameters (optional):
    - exchange: str - Exchange code (default: US)
    - detect_missing: bool - Also detect holidays from price gaps

    Returns:
        Dict with statusCode and body containing update results
    """
    logger.info("Holiday fetcher invoked", extra={'event_keys': list(event.keys())})

    # Handle dry run for smoke tests
    if event.get('dry_run'):
        logger.info("Dry run requested, returning success")
        return {
            'statusCode': 200,
            'body': json.dumps({'dry_run': True, 'status': 'ok'})
        }

    try:
        # Import the core holiday fetcher (api_keys handles Secrets Manager)
        from core.holiday_fetcher import HolidayFetcher

        # Extract parameters
        exchange = event.get('exchange', 'US')
        detect_missing = event.get('detect_missing', False)

        logger.info(
            "Starting holiday fetch",
            extra={'exchange': exchange, 'detect_missing': detect_missing}
        )

        # Run the fetch
        fetcher = HolidayFetcher()
        result = fetcher.fetch(exchange=exchange, detect_missing=detect_missing)

        # Determine status code
        status_code = 200 if result['success'] else 500

        logger.info("Holiday fetch complete", extra=result)

        return {
            'statusCode': status_code,
            'body': json.dumps(result)
        }

    except Exception as e:
        logger.error(
            "Holiday fetch failed",
            extra={'error': type(e).__name__, 'error_message': str(e)},
            exc_info=True
        )
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': type(e).__name__,
                'error_message': str(e)
            })
        }


def validator_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Price data validator Lambda handler.

    Validates price data completeness and identifies gaps.
    Typically run daily at market close.

    Event parameters (optional):
    - symbols: list[str] - Specific symbols to validate (default: all)
    - interval: str - "daily" or "intraday" (default: daily)
    - end_date: str - End date for validation (ISO format, default: today)

    Returns:
        Dict with statusCode and body containing validation results
    """
    logger.info("Price validator invoked", extra={'event_keys': list(event.keys())})

    # Handle dry run for smoke tests
    if event.get('dry_run'):
        logger.info("Dry run requested, returning success")
        return {
            'statusCode': 200,
            'body': json.dumps({'dry_run': True, 'status': 'ok'})
        }

    try:
        # Import the core validator
        from core.validator import PriceValidator
        from db_service import DBService

        # Extract parameters
        symbols: Optional[List[str]] = event.get('symbols')
        interval = event.get('interval', 'daily')
        end_date_str = event.get('end_date')

        # Parse end date
        if end_date_str:
            end_date = date.fromisoformat(end_date_str)
        else:
            end_date = date.today()

        # Get symbols from watchlist if not provided
        if symbols is None:
            db = DBService()
            symbols = db.get_watchlist_symbols(enabled_only=True)

        logger.info(
            "Starting validation",
            extra={
                'symbol_count': len(symbols),
                'interval': interval,
                'end_date': end_date.isoformat()
            }
        )

        # Run validation
        validator = PriceValidator()
        result = validator.validate_symbols(
            symbols=symbols,
            interval=interval,
            end_date=end_date
        )

        # Determine status code
        # 200 if all complete, 207 (multi-status) if some incomplete
        if result['incomplete_count'] > 0:
            status_code = 207
        else:
            status_code = 200

        logger.info(
            "Validation complete",
            extra={
                'complete_count': result['complete_count'],
                'incomplete_count': result['incomplete_count']
            }
        )

        return {
            'statusCode': status_code,
            'body': json.dumps(result)
        }

    except Exception as e:
        logger.error(
            "Validation failed",
            extra={'error': type(e).__name__, 'error_message': str(e)},
            exc_info=True
        )
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': type(e).__name__,
                'error_message': str(e)
            })
        }
