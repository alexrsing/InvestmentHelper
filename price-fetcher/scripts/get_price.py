#!/usr/bin/env python3
"""
CLI tool to retrieve and display stored price data from DynamoDB.

Usage:
    python get_price.py AAPL                          # Show price data for AAPL
    python get_price.py AAPL --interval 1d --range 1w # Show daily prices for last week
    python get_price.py AAPL --interval 15m --limit 10 # Show last 10 15-min prices
    python get_price.py --list                        # List all stored symbols
"""

import argparse
import re
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Add src and fetchers to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "fetchers"))

from pricedata.db_service import DBService
from logging_config import setup_logging, get_logger

logger = get_logger(__name__)

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")


def format_number(value: Any, decimals: int = 2) -> str:
    """Format a number for display."""
    if value is None:
        return "N/A"
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, (int, float)):
        if abs(value) >= 1_000_000:
            return f"{value:,.0f}"
        elif abs(value) >= 1000:
            return f"{value:,.0f}"
        else:
            return f"{value:.{decimals}f}"
    return str(value)


def format_price(value: Any) -> str:
    """Format a price value with dollar sign."""
    if value is None:
        return "N/A"
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, (int, float)):
        return f"${value:,.2f}"
    return str(value)


def format_percent(value: Any) -> str:
    """Format a percentage value with sign."""
    if value is None:
        return "N/A"
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, (int, float)):
        sign = "+" if value >= 0 else ""
        return f"{sign}{value:.2f}%"
    return str(value)


def format_volume(value: Any) -> str:
    """Format volume with commas."""
    if value is None:
        return "N/A"
    if isinstance(value, Decimal):
        value = int(value)
    if isinstance(value, (int, float)):
        return f"{int(value):,}"
    return str(value)


def parse_range(range_str: str) -> Optional[timedelta]:
    """Parse a range string like '2d' or '1w' into a timedelta.

    Args:
        range_str: String like '2d' (2 days), '1w' (1 week), '2w' (2 weeks)

    Returns:
        timedelta object, or None if invalid format
    """
    match = re.match(r'^(\d+)([dwDW])$', range_str)
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2).lower()

    if unit == 'd':
        return timedelta(days=amount)
    elif unit == 'w':
        return timedelta(weeks=amount)

    return None


def filter_history_by_range(
    history: List[Dict[str, Any]],
    range_delta: timedelta
) -> List[Dict[str, Any]]:
    """Filter historical data to only include items within the time range."""
    if not history:
        return []

    cutoff = datetime.now() - range_delta
    filtered = []

    for item in history:
        date_str = item.get('date', '')
        if not date_str:
            continue

        try:
            # Parse various date formats
            if 'T' in date_str:
                item_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if item_date.tzinfo:
                    item_date = item_date.replace(tzinfo=None)
            elif ' ' in date_str:
                item_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            else:
                item_date = datetime.strptime(date_str, "%Y-%m-%d")

            if item_date >= cutoff:
                filtered.append(item)
        except (ValueError, TypeError):
            continue

    return filtered


def display_current_price(data: Dict[str, Any]) -> None:
    """Display current price information."""
    symbol = data.get('etf_symbol', 'Unknown')
    last_updated = data.get('last_updated', 'N/A')
    last_fetched = data.get('last_fetched_at', 'N/A')
    data_source = data.get('data_source', 'N/A')

    current_price = data.get('current_price')
    change_percent = data.get('change_percent')
    volume = data.get('volume')

    logger.info("Symbol: %s", symbol)
    logger.info("Last Updated: %s", last_updated)
    logger.info("Last Fetched: %s", last_fetched)
    logger.info("Data Source: %s", data_source)
    logger.info("")
    logger.info("Current Price: %s", format_price(current_price))
    logger.info("Change: %s", format_percent(change_percent))
    logger.info("Volume: %s", format_volume(volume))


def display_historical_data(
    data: Dict[str, Any],
    interval: str,
    limit: Optional[int] = None,
    range_str: Optional[str] = None
) -> None:
    """Display historical OHLC data."""
    # Map interval to data field
    interval_map = {
        '5m': 'price_history_5m',
        '15m': 'price_history_15min',
        '1d': 'price_history_1d'
    }

    field_name = interval_map.get(interval)
    if not field_name:
        logger.error("Invalid interval '%s'", interval)
        return

    history = data.get(field_name, [])

    if not history:
        logger.info("No historical data available for interval '%s'", interval)
        return

    # Apply range filter if specified
    if range_str:
        range_delta = parse_range(range_str)
        if range_delta:
            history = filter_history_by_range(history, range_delta)
            range_desc = f"last {range_str}"
        else:
            logger.warning("Invalid range format '%s', showing all data", range_str)
            range_desc = "all"
    else:
        range_desc = "all"

    # Apply limit if specified (and no range, since range takes precedence)
    if limit and not range_str:
        history = history[-limit:]  # Take last N items

    if not history:
        logger.info("No historical data found for the specified range")
        return

    # Display header
    logger.info("Historical Prices (%s interval, %s):", interval, range_desc)
    logger.info("-" * 65)

    # Check if we have OHLC data or just close
    has_ohlc = any('open' in item or 'high' in item or 'low' in item for item in history)

    if has_ohlc:
        logger.info("%-20s %10s %10s %10s %10s", 'Date', 'Open', 'High', 'Low', 'Close')
        logger.info("-" * 65)

        for item in history:
            date_str = item.get('date', 'N/A')
            # Truncate date for display
            if len(date_str) > 19:
                date_str = date_str[:19]

            open_price = format_number(item.get('open'), 2)
            high_price = format_number(item.get('high'), 2)
            low_price = format_number(item.get('low'), 2)
            close_price = format_number(item.get('close'), 2)

            logger.info("%-20s %10s %10s %10s %10s", date_str, open_price, high_price, low_price, close_price)
    else:
        # Only close prices available
        logger.info("%-20s %10s", 'Date', 'Close')
        logger.info("-" * 35)

        for item in history:
            date_str = item.get('date', 'N/A')
            if len(date_str) > 19:
                date_str = date_str[:19]

            close_price = format_number(item.get('close'), 2)
            logger.info("%-20s %10s", date_str, close_price)

    logger.info("Total: %d data points", len(history))


def display_symbol_list(records: List[Dict[str, Any]]) -> None:
    """Display list of all stored symbols."""
    if not records:
        logger.info("No stored symbols found.")
        return

    # Sort by symbol
    records.sort(key=lambda x: x.get('etf_symbol', ''))

    logger.info("Stored Symbols (%d total):", len(records))
    logger.info("-" * 70)
    logger.info("%-10s %-28s %-15s", 'Symbol', 'Last Fetched', 'Source')
    logger.info("-" * 70)

    for record in records:
        symbol = record.get('etf_symbol', 'N/A')
        last_fetched = record.get('last_fetched_at', record.get('last_updated', 'N/A'))
        source = record.get('data_source', 'N/A')

        # Truncate last_fetched for display
        if last_fetched and len(str(last_fetched)) > 26:
            last_fetched = str(last_fetched)[:26]

        logger.info("%-10s %-28s %-15s", symbol, str(last_fetched), source)


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Retrieve and display stored price data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python get_price.py AAPL                           # Show price data for AAPL
  python get_price.py AAPL --interval 1d --range 1w  # Daily prices for last week
  python get_price.py AAPL --interval 15m --limit 10 # Last 10 15-min prices
  python get_price.py --list                         # List all stored symbols
        """
    )

    parser.add_argument(
        'symbol',
        nargs='?',
        help='ETF/stock symbol to query'
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all stored symbols'
    )

    parser.add_argument(
        '--interval', '-i',
        choices=['5m', '15m', '1d'],
        default='1d',
        help='Historical data interval (default: 1d)'
    )

    parser.add_argument(
        '--limit', '-n',
        type=int,
        help='Number of historical data points to show'
    )

    parser.add_argument(
        '--range', '-r',
        dest='range_str',
        help='Time range for historical data (e.g., 2d, 1w, 2w)'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.list and not args.symbol:
        parser.error("Please provide a symbol or use --list")

    # Initialize database service
    db_service = DBService()

    # Handle --list command
    if args.list:
        records = db_service.get_all_price_records()
        display_symbol_list(records)
        return

    # Get price data for symbol
    symbol = args.symbol.upper()
    data = db_service.get_price_data(symbol)

    if not data:
        logger.warning("No stored data found for symbol '%s'", symbol)
        logger.info("Run the price fetcher to retrieve data for this symbol.")
        sys.exit(1)

    # Display current price data
    display_current_price(data)

    # Display historical data if requested or by default
    display_historical_data(
        data,
        interval=args.interval,
        limit=args.limit,
        range_str=args.range_str
    )


if __name__ == "__main__":
    main()
