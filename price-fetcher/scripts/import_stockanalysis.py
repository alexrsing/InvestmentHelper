#!/usr/bin/env python3
"""
CLI tool to import price history data from StockAnalysis.com JSON files.

Usage:
    python scripts/import_stockanalysis.py /path/to/data/directory
    python scripts/import_stockanalysis.py /path/to/data --symbols AAPL,MSFT,GOOGL
    python scripts/import_stockanalysis.py /path/to/data --dry-run

Options:
    --symbols, -s    Comma-separated list of symbols to import (default: all)
    --dry-run, -n    Show what would be imported without writing to database
    --days, -d       Number of days of history to import (default: 0 = all)
    --force, -f      Force import even if data already exists
"""

import argparse
import datetime as dt
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add fetchers directory to path
fetchers_dir = Path(__file__).parent.parent / "fetchers"
sys.path.insert(0, str(fetchers_dir))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

from sa_service import StockAnalysisService
from db_service import DBService
from logging_config import setup_logging, get_logger

logger = get_logger(__name__)


def convert_floats_to_decimal(obj: Any) -> Any:
    """Recursively convert all float values to Decimal for DynamoDB compatibility."""
    import math

    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    return obj


def import_symbol(
    sa_service: StockAnalysisService,
    db_service: DBService,
    symbol: str,
    data_dir: str,
    days: int = 0,
    dry_run: bool = False
) -> bool:
    """
    Import price history for a single symbol.

    Args:
        sa_service: StockAnalysis service instance
        db_service: Database service instance
        symbol: Symbol to import
        data_dir: Directory containing the JSON files
        days: Number of days to import (0 = all)
        dry_run: If True, don't write to database

    Returns:
        True if successful
    """
    # Get price history
    history = sa_service.get_price_history_1d(symbol, data_dir, days=days)
    if not history:
        logger.warning("No data found for %s", symbol)
        return False

    # Get current info (most recent data point)
    info = sa_service.get_info(symbol, data_dir)

    # Get date range
    date_range = sa_service.get_date_range(symbol, data_dir)

    # Build the record
    now = dt.datetime.now(dt.timezone.utc)
    current_date = now.date().isoformat()
    current_timestamp = now.isoformat()

    record = {
        'etf_symbol': symbol.upper(),
        'last_updated': current_date,
        'last_fetched_at': current_timestamp,
        'data_source': 'stockanalysis',
        'current_price': convert_floats_to_decimal(info.get('regularMarketPrice') if info else None),
        'change_percent': convert_floats_to_decimal(info.get('regularMarketChangePercent') if info else None),
        'volume': convert_floats_to_decimal(info.get('volume') if info else None),
        'price_history_1d': convert_floats_to_decimal(history),
    }

    if dry_run:
        logger.info("Would import %s: %d data points", symbol, len(history))
        if date_range:
            logger.info("  Date range: %s to %s", date_range[0], date_range[1])
        if info:
            logger.info("  Latest price: $%s", info.get('regularMarketPrice', 'N/A'))
        return True

    # Write to database
    try:
        db_service.put_item(record)
        logger.info("Imported %s: %d data points", symbol, len(history))
        return True
    except Exception as e:
        logger.error("Error importing %s: %s", symbol, e)
        return False


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Import price history from StockAnalysis.com JSON files"
    )
    parser.add_argument(
        "data_dir",
        help="Directory containing StockAnalysis JSON files"
    )
    parser.add_argument(
        "--symbols", "-s",
        default=None,
        help="Comma-separated list of symbols to import (default: all)"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be imported without writing to database"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=0,
        help="Number of days of history to import (default: 0 = all)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force import even if data already exists"
    )
    args = parser.parse_args()

    # Validate data directory
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error("Directory not found: %s", data_dir)
        return 1

    if not data_dir.is_dir():
        logger.error("Not a directory: %s", data_dir)
        return 1

    logger.info("StockAnalysis Price History Importer")
    logger.info("=" * 50)
    logger.info("Data directory: %s", data_dir)
    if args.dry_run:
        logger.info("Mode: DRY RUN (no changes will be made)")
    logger.info("")

    # Initialize services
    sa_service = StockAnalysisService(str(data_dir))

    if not args.dry_run:
        db_service = DBService()
    else:
        db_service = None

    # Get list of symbols to import
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
        # Validate symbols exist in data directory
        available = set(sa_service.list_symbols())
        missing = [s for s in symbols if s not in available]
        if missing:
            logger.warning("Symbols not found in data directory: %s", ', '.join(missing))
        symbols = [s for s in symbols if s in available]
    else:
        symbols = sa_service.list_symbols()

    if not symbols:
        logger.warning("No symbols found to import")
        return 1

    logger.info("Symbols to import: %d", len(symbols))
    if args.days > 0:
        logger.info("Days of history: %d", args.days)
    else:
        logger.info("Days of history: all available")
    logger.info("")

    # Import each symbol
    success_count = 0
    fail_count = 0

    for i, symbol in enumerate(symbols, 1):
        logger.info("[%d/%d] %s", i, len(symbols), symbol)
        if import_symbol(sa_service, db_service, symbol, str(data_dir), args.days, args.dry_run):
            success_count += 1
        else:
            fail_count += 1

    # Summary
    logger.info("")
    logger.info("=" * 50)
    logger.info("Import complete!")
    logger.info("  Successful: %d", success_count)
    if fail_count:
        logger.info("  Failed: %d", fail_count)

    if args.dry_run:
        logger.info("")
        logger.info("This was a dry run. No data was written to the database.")
        logger.info("Run without --dry-run to perform the actual import.")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
