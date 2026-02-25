"""
Public API for pricedata package.

Read operations:
    get_price(symbol, date) -> float | None
    get_price_history(symbol, start, end) -> dict[date, float]
    get_current_price(symbol) -> float | None
    list_symbols() -> list[str]

Holiday operations:
    is_market_holiday(date) -> bool
    get_market_holidays(start, end) -> list[dict]
    load_holidays() -> dict

Write operations:
    store_price(symbol, date, price) -> bool
    store_price_history(symbol, history: dict[date, float]) -> bool
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from decimal import Decimal

from .db_service import DBService

logger = logging.getLogger(__name__)

_db: Optional[DBService] = None


def _get_db() -> DBService:
    """Lazy initialization of DB connection."""
    global _db
    if _db is None:
        _db = DBService()
    return _db


# ============ READ OPERATIONS ============


def get_price(symbol: str, target_date: date) -> Optional[float]:
    """
    Get closing price for a symbol on a specific date.

    Args:
        symbol: Stock/ETF ticker symbol (e.g., "AAPL")
        target_date: Date to get price for

    Returns:
        Closing price as float, or None if not found

    Note:
        If target_date is a weekend/holiday, returns the most recent
        trading day's closing price before that date.
    """
    db = _get_db()
    data = db.get_price_data(symbol.upper())

    if not data:
        return None

    history = data.get('price_history_1d', [])
    return _find_price_on_or_before(history, target_date)


def get_price_history(
    symbol: str,
    start_date: date,
    end_date: date
) -> dict[date, float]:
    """
    Get price history for a symbol over a date range.

    Args:
        symbol: Stock/ETF ticker symbol
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        Dict mapping dates to closing prices
    """
    db = _get_db()
    data = db.get_price_data(symbol.upper())

    if not data:
        return {}

    history = data.get('price_history_1d', [])
    return _extract_date_range(history, start_date, end_date)


def get_current_price(symbol: str) -> Optional[float]:
    """Get the most recent price for a symbol."""
    db = _get_db()
    data = db.get_price_data(symbol.upper())

    if not data:
        return None

    price = data.get('current_price')
    if isinstance(price, Decimal):
        return float(price)
    return price


def list_symbols() -> list[str]:
    """List all symbols with stored price data."""
    db = _get_db()
    records = db.get_all_price_records()
    return sorted([r.get('etf_symbol', '') for r in records if r.get('etf_symbol')])


# ============ HOLIDAY OPERATIONS ============

_holidays_cache: Optional[dict] = None


def _get_holidays_file_path() -> Path:
    """Get the path to the market holidays JSON file."""
    # Look for config/market_holidays.json relative to the package
    package_dir = Path(__file__).parent
    project_root = package_dir.parent.parent
    return project_root / "config" / "market_holidays.json"


def _load_holidays_from_dynamodb(exchange: str = 'US') -> Optional[dict]:
    """
    Load holidays from DynamoDB config table.

    Args:
        exchange: Exchange code (default: 'US')

    Returns:
        Holiday data dict or None if not available
    """
    try:
        # Add fetchers to path for import
        import sys
        fetchers_path = Path(__file__).parent.parent.parent / 'fetchers'
        if str(fetchers_path) not in sys.path:
            sys.path.insert(0, str(fetchers_path))

        from config_service import get_cached_config
        data = get_cached_config('holidays', exchange)
        if data:
            logger.debug("Loaded holidays from DynamoDB", extra={'exchange': exchange})
        return data
    except Exception as e:
        logger.debug(
            "Could not load holidays from DynamoDB: %s",
            type(e).__name__
        )
        return None


def _load_holidays_from_file() -> Optional[dict]:
    """
    Load holidays from local JSON file.

    Returns:
        Holiday data dict or None if file not found
    """
    holidays_path = _get_holidays_file_path()
    if not holidays_path.exists():
        return None

    try:
        with open(holidays_path) as f:
            data = json.load(f)
            logger.debug("Loaded holidays from file", extra={'path': str(holidays_path)})
            return data
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("Failed to load holidays from file: %s", e)
        return None


def load_holidays() -> dict:
    """
    Load market holidays with DynamoDB-first, file fallback strategy.

    In Lambda: Loads from DynamoDB config table
    Locally: Tries DynamoDB first, falls back to local JSON file

    Returns:
        Dict with 'holidays' list and metadata, or empty dict if not found.
        Each holiday has: atDate, eventName, tradingHour, source
    """
    global _holidays_cache
    if _holidays_cache is not None:
        return _holidays_cache

    import os
    is_lambda = bool(os.getenv('AWS_LAMBDA_FUNCTION_NAME'))

    # Try DynamoDB first
    data = _load_holidays_from_dynamodb()

    # Fall back to local file if not in Lambda and DynamoDB failed
    if data is None and not is_lambda:
        data = _load_holidays_from_file()

    _holidays_cache = data if data else {}
    return _holidays_cache


def clear_holidays_cache() -> None:
    """Clear the holidays cache (useful for testing or forced refresh)."""
    global _holidays_cache
    _holidays_cache = None


def is_market_holiday(target_date: date) -> bool:
    """
    Check if a date is a market holiday.

    Args:
        target_date: Date to check

    Returns:
        True if the date is a known market holiday (full closure)
    """
    holidays = load_holidays()
    if not holidays.get("holidays"):
        return False

    target_str = target_date.isoformat()
    for holiday in holidays["holidays"]:
        if holiday.get("atDate") == target_str:
            # Full closure if no trading hours specified
            return not holiday.get("tradingHour")
    return False


def is_early_close(target_date: date) -> Optional[str]:
    """
    Check if a date is an early market close day.

    Args:
        target_date: Date to check

    Returns:
        Trading hours string if early close, None otherwise
    """
    holidays = load_holidays()
    if not holidays.get("holidays"):
        return None

    target_str = target_date.isoformat()
    for holiday in holidays["holidays"]:
        if holiday.get("atDate") == target_str:
            trading_hour = holiday.get("tradingHour", "")
            return trading_hour if trading_hour else None
    return None


def get_market_holidays(
    start_date: date,
    end_date: date
) -> list[dict]:
    """
    Get market holidays within a date range.

    Args:
        start_date: Start of range (inclusive)
        end_date: End of range (inclusive)

    Returns:
        List of holiday dicts with atDate, eventName, tradingHour, source
    """
    holidays = load_holidays()
    if not holidays.get("holidays"):
        return []

    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    return [
        h for h in holidays["holidays"]
        if start_str <= h.get("atDate", "") <= end_str
    ]


def is_trading_day(target_date: date) -> bool:
    """
    Check if a date is a trading day (not weekend, not holiday).

    Args:
        target_date: Date to check

    Returns:
        True if the market is open on this date
    """
    # Check if weekend (Monday=0, Sunday=6)
    if target_date.weekday() >= 5:
        return False

    # Check if holiday
    if is_market_holiday(target_date):
        return False

    return True


# ============ WRITE OPERATIONS ============


def store_price(symbol: str, price_date: date, price: float) -> bool:
    """
    Store a single price point.

    Args:
        symbol: Stock/ETF ticker symbol
        price_date: Date of the price
        price: Closing price

    Returns:
        True if successful
    """
    return store_price_history(symbol, {price_date: price})


def store_price_history(
    symbol: str,
    history: dict[date, float],
    source: str = "manual"
) -> bool:
    """
    Store multiple price points for a symbol.

    Args:
        symbol: Stock/ETF ticker symbol
        history: Dict mapping dates to prices
        source: Data source identifier

    Returns:
        True if successful
    """
    db = _get_db()
    symbol = symbol.upper()

    # Get existing data or create new record
    existing = db.get_price_data(symbol) or {}

    # Get existing history or empty list
    existing_history = existing.get('price_history_1d', [])

    # Convert existing history to dict for merging
    history_dict = {}
    for item in existing_history:
        item_date = item.get('date', '')[:10]
        if item_date:
            history_dict[item_date] = item.get('close')

    # Merge new history
    for price_date, price in history.items():
        date_str = price_date.isoformat()
        history_dict[date_str] = price

    # Convert back to list format
    new_history = [
        {'date': d, 'close': Decimal(str(p))}
        for d, p in sorted(history_dict.items())
    ]

    # Get the most recent price for current_price field
    current_price = None
    if new_history:
        current_price = new_history[-1]['close']

    # Build the record
    now = datetime.now()
    record = {
        'etf_symbol': symbol,
        'last_updated': now.date().isoformat(),
        'last_fetched_at': now.isoformat(),
        'data_source': source,
        'current_price': current_price,
        'price_history_1d': new_history,
    }

    # Preserve other fields from existing record
    for key in ['change_percent', 'volume', 'price_history_15min', 'price_history_5m']:
        if key in existing:
            record[key] = existing[key]

    try:
        db.put_item(record)
        return True
    except Exception as e:
        logger.error("Error storing price history: %s", e, extra={'symbol': symbol})
        return False


# ============ INTERNAL HELPERS ============


def _find_price_on_or_before(history: list, target_date: date) -> Optional[float]:
    """Find the closest price on or before target_date."""
    target_str = target_date.isoformat()
    best_price = None
    best_date = None

    for item in history:
        item_date = item.get('date', '')[:10]
        if item_date <= target_str:
            if best_date is None or item_date > best_date:
                best_date = item_date
                price = item.get('close')
                if isinstance(price, Decimal):
                    price = float(price)
                best_price = price

    return best_price


def _extract_date_range(
    history: list,
    start_date: date,
    end_date: date
) -> dict[date, float]:
    """Extract prices within a date range."""
    result = {}
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    for item in history:
        item_date_str = item.get('date', '')[:10]
        if start_str <= item_date_str <= end_str:
            try:
                item_date = date.fromisoformat(item_date_str)
                price = item.get('close')
                if isinstance(price, Decimal):
                    price = float(price)
                if price is not None:
                    result[item_date] = price
            except ValueError:
                continue

    return result
