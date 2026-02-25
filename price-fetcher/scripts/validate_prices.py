#!/usr/bin/env python3
"""
Price history completeness validator.

Validates that price data exists for symbols in trade history or positions CSV file(s).

Daily validation:
    - Checks for price data on every trading day since the first trade
    - Excludes weekends and market holidays

Intraday validation:
    - Checks for 5-minute interval data for the past 10 calendar days
    - Validates all 5-minute bars during regular trading hours (9:30 AM - 4:00 PM ET)
    - Handles early market close days (e.g., day before Independence Day)
    - Excludes weekends and market holidays

Usage:
    python scripts/validate_prices.py trades.csv --interval daily
    python scripts/validate_prices.py positions.csv --interval intraday
    python scripts/validate_prices.py "data/Accounts_History_*.csv" --output missing.csv
    python scripts/validate_prices.py file1.csv file2.csv file3.csv
    python scripts/validate_prices.py trades.csv --exclude-file excluded_symbols.txt

Options:
    --interval, -i     Interval to check: daily or intraday (default: daily)
    --output, -o       Output CSV file for symbols needing backfill
    --exclude-file     File containing symbols to exclude (one per line)
    --exclude          Comma-separated symbols to exclude
    --verbose, -v      Show detailed output
    --detailed-output  Include missing date/interval details in output CSV
"""

import argparse
import csv
import glob
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Add src directory to path for pricedata package
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

# Add fetchers directory to path for logging_config
fetchers_dir = Path(__file__).parent.parent / "fetchers"
sys.path.insert(0, str(fetchers_dir))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

from logging_config import setup_logging, get_logger

logger = get_logger(__name__)

# Default config file path
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "validator_config.json"


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load validator configuration from JSON file."""
    path = config_path or DEFAULT_CONFIG_PATH
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"excluded_symbols": []}


def save_config(config: Dict[str, Any], config_path: Optional[Path] = None) -> bool:
    """Save validator configuration to JSON file."""
    path = config_path or DEFAULT_CONFIG_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except IOError:
        return False


def parse_date(date_str: str) -> Optional[date]:
    """Parse date from various formats."""
    formats = [
        "%m/%d/%Y",  # Fidelity format: 03/31/2025
        "%Y-%m-%d",  # ISO format: 2025-03-31
        "%m-%d-%Y",  # Alt format: 03-31-2025
        "%d/%m/%Y",  # European format: 31/03/2025
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def read_trade_history(csv_path: Path) -> List[Dict[str, Any]]:
    """
    Read trade history or positions from CSV file.

    Handles flexible column ordering and various CSV formats.
    Supports both trade history files (with dates) and positions files (without dates).

    Returns:
        List of trade dicts with 'date', 'symbol', 'action' keys
        For positions files without dates, uses a default date of 10 years ago
    """
    trades = []

    # Try different encodings
    encodings = ['utf-8-sig', 'utf-8', 'latin-1']

    for encoding in encodings:
        try:
            with open(csv_path, 'r', encoding=encoding) as f:
                # Read all lines and skip empty ones at the start
                lines = f.readlines()

            # Find the header line (first non-empty line)
            header_idx = 0
            for i, line in enumerate(lines):
                if line.strip():
                    header_idx = i
                    break

            # Parse CSV from the header line onwards
            content = ''.join(lines[header_idx:])

            reader = csv.DictReader(content.splitlines())

            # Normalize column names (case-insensitive lookup)
            fieldnames = reader.fieldnames or []
            col_map = {name.lower().strip(): name for name in fieldnames}

            # Find the relevant columns
            date_col = None
            symbol_col = None
            action_col = None

            # Try various column name variations
            date_variations = ['run date', 'date', 'trade date', 'transaction date']
            symbol_variations = ['symbol', 'ticker', 'security']
            action_variations = ['action', 'trade', 'transaction', 'type', 'activity']

            for var in date_variations:
                if var in col_map:
                    date_col = col_map[var]
                    break

            for var in symbol_variations:
                if var in col_map:
                    symbol_col = col_map[var]
                    break

            for var in action_variations:
                if var in col_map:
                    action_col = col_map[var]
                    break

            # Symbol column is required, but date column is optional (positions file)
            if not symbol_col:
                raise ValueError(f"Required 'Symbol' column not found. Found: {fieldnames}")

            # If no date column, this is a positions file - use a default date
            is_positions_file = (date_col is None)
            default_date = date.today() - timedelta(days=3650)  # 10 years ago

            for row in reader:
                symbol = (row.get(symbol_col) or '').strip().upper()

                # Skip rows without symbol (cash transactions, etc.)
                if not symbol:
                    continue

                # Skip symbols that end with ** (money market funds in Fidelity exports)
                if symbol.endswith('**'):
                    continue

                if is_positions_file:
                    # Positions file - use default date
                    trade_date = default_date
                    action = ''
                else:
                    # Trade history file - parse date
                    date_str = (row.get(date_col) or '').strip()
                    action = (row.get(action_col) or '').strip() if action_col else ''

                    trade_date = parse_date(date_str)
                    if not trade_date:
                        continue

                trades.append({
                    'date': trade_date,
                    'symbol': symbol,
                    'action': action
                })

            return trades

        except UnicodeDecodeError:
            continue
        except csv.Error as e:
            logger.warning("CSV parsing error with %s: %s", encoding, e)
            continue

    raise ValueError(f"Could not parse CSV file: {csv_path}")


def get_symbols_first_trade_dates(trades: List[Dict[str, Any]]) -> Dict[str, date]:
    """
    Extract unique symbols and their first trade dates.

    Returns:
        Dict mapping symbol to first trade date
    """
    first_dates: Dict[str, date] = {}

    for trade in trades:
        symbol = trade['symbol']
        trade_date = trade['date']

        if symbol not in first_dates or trade_date < first_dates[symbol]:
            first_dates[symbol] = trade_date

    return first_dates


def get_trading_days(start_date: date, end_date: date) -> Set[date]:
    """
    Get all trading days between start and end dates.

    Excludes weekends and market holidays.
    """
    from pricedata import is_trading_day

    trading_days = set()
    current = start_date

    while current <= end_date:
        if is_trading_day(current):
            trading_days.add(current)
        current += timedelta(days=1)

    return trading_days


def get_price_dates(symbol: str, start_date: date, end_date: date) -> Set[date]:
    """Get dates with price data for a symbol."""
    from pricedata import get_price_history

    history = get_price_history(symbol, start_date, end_date)
    return set(history.keys())


def validate_symbol_daily(
    symbol: str,
    first_trade_date: date,
    end_date: date,
    verbose: bool = False
) -> Tuple[bool, List[date]]:
    """
    Validate daily price history completeness for a symbol.

    Args:
        symbol: Stock/ETF symbol
        first_trade_date: First trade date for this symbol
        end_date: End date for validation (usually today)
        verbose: Print detailed output

    Returns:
        Tuple of (is_complete, list_of_missing_dates)
    """
    # Get expected trading days
    expected_days = get_trading_days(first_trade_date, end_date)

    # Get actual price dates
    actual_dates = get_price_dates(symbol, first_trade_date, end_date)

    # Find missing dates
    missing_dates = sorted(expected_days - actual_dates)

    if verbose and missing_dates:
        logger.info("  %s: %d missing days", symbol, len(missing_dates))
        if len(missing_dates) <= 10:
            for d in missing_dates:
                logger.info("    - %s", d)
        else:
            logger.info("    First 5: %s", [str(d) for d in missing_dates[:5]])
            logger.info("    Last 5: %s", [str(d) for d in missing_dates[-5:]])

    return len(missing_dates) == 0, missing_dates


def get_expected_intraday_intervals(target_date: date) -> Set[str]:
    """
    Get expected 5-minute interval timestamps for a trading day.

    Regular hours: 9:30 AM - 4:00 PM ET (78 intervals)
    Early close: 9:30 AM - 1:00 PM ET (43 intervals)

    Args:
        target_date: Trading day to generate intervals for

    Returns:
        Set of ISO timestamp strings (e.g., "2025-01-22T09:30:00")
    """
    from pricedata import is_early_close

    intervals = set()

    # Check for early close
    early_close_hours = is_early_close(target_date)

    if early_close_hours:
        # Parse early close time from format "09:30-13:00"
        parts = early_close_hours.split('-')
        if len(parts) == 2:
            market_close_str = parts[1].strip()
        else:
            # Fallback to regular hours if parsing fails
            market_close_str = "16:00"
    else:
        # Regular trading hours: close at 4:00 PM
        market_close_str = "16:00"

    # Parse close time
    close_hour, close_minute = map(int, market_close_str.split(':'))

    # Market opens at 9:30 AM
    current_hour = 9
    current_minute = 30

    # Generate 5-minute intervals from 9:30 to market close
    while True:
        # Create timestamp
        timestamp = f"{target_date}T{current_hour:02d}:{current_minute:02d}:00"
        intervals.add(timestamp)

        # Stop if we've reached the last interval before close
        # Market close is exclusive (e.g., 16:00 means last bar is 15:55)
        if current_hour == close_hour and current_minute == close_minute:
            break

        # Increment by 5 minutes
        current_minute += 5
        if current_minute >= 60:
            current_minute = 0
            current_hour += 1

        # Safety check: don't go past 4:00 PM
        if current_hour > 16:
            break

    return intervals


def validate_symbol_intraday(
    symbol: str,
    first_trade_date: date,
    end_date: date,
    verbose: bool = False
) -> Tuple[bool, List[str]]:
    """
    Validate 5-minute intraday price history completeness for a symbol.

    Checks that all 5-minute intervals exist for each trading day
    in the past 10 calendar days.

    Args:
        symbol: Stock/ETF symbol
        first_trade_date: First trade date (ignored for intraday - uses 10-day window)
        end_date: End date for validation
        verbose: Print detailed output

    Returns:
        Tuple of (is_complete, list_of_missing_intervals)
        Missing intervals are formatted as "YYYY-MM-DD HH:MM"
    """
    from pricedata.client import _get_db

    db = _get_db()
    data = db.get_price_data(symbol.upper())

    # Calculate 10 calendar days window
    start_date = end_date - timedelta(days=10)

    # Get trading days in the window
    expected_trading_days = get_trading_days(start_date, end_date)

    if not data:
        if verbose:
            logger.info("  %s: No data found", symbol)
        # Generate all expected intervals as missing
        all_intervals = set()
        for day in expected_trading_days:
            all_intervals.update(get_expected_intraday_intervals(day))
        return False, sorted(all_intervals)

    # Check for 5-minute data
    history_5m = data.get('price_history_5m', [])

    if not history_5m:
        if verbose:
            logger.info("  %s: No 5-minute data", symbol)
        # Generate all expected intervals as missing
        all_intervals = set()
        for day in expected_trading_days:
            all_intervals.update(get_expected_intraday_intervals(day))
        return False, sorted(all_intervals)

    # Extract actual intervals from 5-minute data
    actual_intervals = set()
    for item in history_5m:
        timestamp = item.get('date', '')
        if timestamp:
            # Normalize to remove microseconds if present
            # Expected format: "2025-01-22T09:30:00" or "2025-01-22T09:30:00.000000"
            if len(timestamp) > 19:
                timestamp = timestamp[:19]
            actual_intervals.add(timestamp)

    # Build expected intervals for all trading days
    expected_intervals = set()
    for day in expected_trading_days:
        expected_intervals.update(get_expected_intraday_intervals(day))

    # Find missing intervals
    missing_intervals = sorted(expected_intervals - actual_intervals)

    if verbose:
        if missing_intervals:
            logger.info("  %s: %d missing 5m intervals across %d trading days", symbol, len(missing_intervals), len(expected_trading_days))
            if len(missing_intervals) <= 10:
                for interval in missing_intervals[:10]:
                    logger.info("    - %s", interval)
            else:
                logger.info("    First 5: %s", missing_intervals[:5])
                logger.info("    Last 5: %s", missing_intervals[-5:])
        else:
            logger.info("  %s: Complete (%d intervals)", symbol, len(actual_intervals))

    return len(missing_intervals) == 0, missing_intervals


def write_output_csv(
    results: List[Dict[str, Any]],
    output_path: Path,
    include_dates: bool = False,
    is_intraday: bool = False
) -> bool:
    """
    Write validation results to CSV file.

    Args:
        results: List of result dicts with 'symbol', 'missing_dates', etc.
        output_path: Path to output CSV
        include_dates: Include missing date/interval details in output
        is_intraday: True if validating intraday intervals (vs daily dates)

    Returns:
        True if successful
    """
    try:
        with open(output_path, 'w', newline='') as f:
            if include_dates:
                if is_intraday:
                    fieldnames = ['Symbol', 'Missing_Count', 'Sample_Missing_Intervals']
                else:
                    fieldnames = ['Symbol', 'First_Trade_Date', 'Missing_Count', 'First_Missing', 'Last_Missing']
            else:
                fieldnames = ['Symbol']

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                if include_dates:
                    missing = result.get('missing_dates', [])
                    if is_intraday:
                        # For intraday, show sample of missing intervals
                        sample_count = min(5, len(missing))
                        sample_intervals = ', '.join(str(m) for m in missing[:sample_count])
                        if len(missing) > sample_count:
                            sample_intervals += ', ...'
                        writer.writerow({
                            'Symbol': result['symbol'],
                            'Missing_Count': len(missing),
                            'Sample_Missing_Intervals': sample_intervals
                        })
                    else:
                        # For daily, show date range
                        writer.writerow({
                            'Symbol': result['symbol'],
                            'First_Trade_Date': result.get('first_trade_date', ''),
                            'Missing_Count': len(missing),
                            'First_Missing': str(missing[0]) if missing else '',
                            'Last_Missing': str(missing[-1]) if missing else ''
                        })
                else:
                    writer.writerow({'Symbol': result['symbol']})

        return True
    except IOError as e:
        logger.error("Error writing output: %s", e)
        return False


def expand_file_patterns(patterns: List[str]) -> List[Path]:
    """
    Expand file patterns (including globs) to a list of file paths.

    Args:
        patterns: List of file paths or glob patterns

    Returns:
        List of Path objects for existing files
    """
    files = []
    for pattern in patterns:
        # Try glob expansion
        expanded = glob.glob(pattern)
        if expanded:
            files.extend(Path(f) for f in expanded)
        else:
            # No glob match, treat as literal path
            files.append(Path(pattern))

    # Remove duplicates while preserving order
    seen = set()
    unique_files = []
    for f in files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_files.append(f)

    return unique_files


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Validate price history completeness for traded symbols"
    )
    parser.add_argument(
        "trade_history",
        nargs="+",
        help="Path(s) to trade history CSV file(s). Supports glob patterns like 'data/*.csv'"
    )
    parser.add_argument(
        "--interval", "-i",
        choices=["daily", "intraday"],
        default="daily",
        help="Price interval to validate (default: daily)"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output CSV file for symbols needing backfill"
    )
    parser.add_argument(
        "--exclude-file",
        default=None,
        help="File containing symbols to exclude (one per line)"
    )
    parser.add_argument(
        "--exclude", "-e",
        default=None,
        help="Comma-separated symbols to exclude"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="End date for validation (default: today, format: YYYY-MM-DD)"
    )
    parser.add_argument(
        "--detailed-output",
        action="store_true",
        help="Include missing date details in output CSV"
    )
    args = parser.parse_args()

    # Expand glob patterns and validate files
    trade_history_files = expand_file_patterns(args.trade_history)

    if not trade_history_files:
        logger.error("No files matched the pattern(s): %s", args.trade_history)
        return 1

    # Check that all files exist
    missing_files = [f for f in trade_history_files if not f.exists()]
    if missing_files:
        logger.error("File(s) not found: %s", [str(f) for f in missing_files])
        return 1

    logger.info("Price History Completeness Validator")
    logger.info("=" * 50)
    if len(trade_history_files) == 1:
        logger.info("Trade history: %s", trade_history_files[0])
    else:
        logger.info("Trade history files: %d", len(trade_history_files))
        for f in trade_history_files:
            logger.info("  - %s", f.name)
    logger.info("Interval: %s", args.interval)
    logger.info("")

    # Load excluded symbols from config
    config = load_config()
    excluded_symbols: Set[str] = set(config.get("excluded_symbols", []))

    # Add symbols from exclude file
    if args.exclude_file:
        exclude_file = Path(args.exclude_file)
        if exclude_file.exists():
            with open(exclude_file) as f:
                for line in f:
                    symbol = line.strip().upper()
                    if symbol and not symbol.startswith('#'):
                        excluded_symbols.add(symbol)

    # Add symbols from command line
    if args.exclude:
        for symbol in args.exclude.split(','):
            excluded_symbols.add(symbol.strip().upper())

    if excluded_symbols:
        logger.info("Excluded symbols: %d", len(excluded_symbols))
        if args.verbose:
            logger.info("  %s", ', '.join(sorted(excluded_symbols)))
        logger.info("")

    # Parse end date
    if args.end_date:
        end_date = date.fromisoformat(args.end_date)
    else:
        end_date = date.today()

    # Read trade history from all files
    logger.info("Reading trade history...")
    all_trades: List[Dict[str, Any]] = []
    for trade_file in trade_history_files:
        try:
            trades = read_trade_history(trade_file)
            all_trades.extend(trades)
            if args.verbose:
                logger.info("  %s: %d trades", trade_file.name, len(trades))
        except ValueError as e:
            logger.error("Error reading %s: %s", trade_file, e)
            return 1

    trades = all_trades
    logger.info("  Found %d trades total", len(trades))

    # Get symbols and first trade dates
    symbols_first_dates = get_symbols_first_trade_dates(trades)
    logger.info("  Unique symbols: %d", len(symbols_first_dates))

    # Filter out excluded symbols
    symbols_to_check = {
        s: d for s, d in symbols_first_dates.items()
        if s not in excluded_symbols
    }
    logger.info("  Symbols to validate: %d", len(symbols_to_check))
    logger.info("")

    # Validate each symbol
    logger.info("Validating %s price history...", args.interval)
    results: List[Dict[str, Any]] = []
    complete_count = 0
    incomplete_count = 0

    validator_func = validate_symbol_daily if args.interval == "daily" else validate_symbol_intraday

    for i, (symbol, first_trade_date) in enumerate(sorted(symbols_to_check.items()), 1):
        if args.verbose:
            logger.info("[%d/%d] %s (first trade: %s)", i, len(symbols_to_check), symbol, first_trade_date)

        is_complete, missing_dates = validator_func(
            symbol, first_trade_date, end_date, args.verbose
        )

        if is_complete:
            complete_count += 1
        else:
            incomplete_count += 1
            results.append({
                'symbol': symbol,
                'first_trade_date': first_trade_date,
                'missing_dates': missing_dates
            })

    # Summary
    logger.info("")
    logger.info("=" * 50)
    logger.info("Validation Summary")
    logger.info("  Complete: %d", complete_count)
    logger.info("  Incomplete: %d", incomplete_count)

    if results:
        logger.info("")
        logger.info("Symbols requiring backfill:")
        for result in results:
            missing = result['missing_dates']
            if args.interval == "intraday":
                # For intraday, missing contains timestamp strings
                if missing:
                    first_interval = missing[0][:16] if len(missing[0]) > 16 else missing[0]  # Trim to YYYY-MM-DD HH:MM
                    last_interval = missing[-1][:16] if len(missing[-1]) > 16 else missing[-1]
                    logger.info("  %s: %d missing 5m intervals (%s to %s)", result['symbol'], len(missing), first_interval, last_interval)
                else:
                    logger.info("  %s: No intervals", result['symbol'])
            else:
                # For daily, missing contains date objects
                logger.info("  %s: %d missing days (%s to %s)", result['symbol'], len(missing), missing[0], missing[-1])

    # Write output CSV
    if args.output and results:
        output_path = Path(args.output)
        logger.info("")
        logger.info("Writing results to %s...", output_path)
        is_intraday = (args.interval == "intraday")
        if write_output_csv(results, output_path, args.detailed_output, is_intraday):
            logger.info("  Done!")
        else:
            logger.error("  Failed to write output")
            return 1

    return 0 if incomplete_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
