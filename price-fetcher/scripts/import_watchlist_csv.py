#!/usr/bin/env python3
"""
Import symbols from a CSV file into the watchlist DynamoDB table.

Usage:
    python scripts/import_watchlist_csv.py symbols.csv
    python scripts/import_watchlist_csv.py symbols.csv --dry-run
    python scripts/import_watchlist_csv.py symbols.csv --symbol-column Ticker --type-column Type

    # Fidelity Portfolio Positions export
    python scripts/import_watchlist_csv.py ~/data/fidelity/Portfolio_Positions.csv --fidelity

CSV Format (minimal - just symbols):
    symbol
    AAPL
    GOOGL
    SPY

CSV Format (with metadata):
    symbol,symbol_type,name,priority
    AAPL,equity,Apple Inc,100
    SPY,etf,SPDR S&P 500 ETF,50
    ^VIX,index,CBOE Volatility Index,10

Fidelity Format:
    Account Number,Account Name,Symbol,Description,Quantity,...,Type
    Z03906797,Primary Brokerage,GOOGL,ALPHABET INC CAP STK CL A,47,...,Margin

Environment:
    WATCHLIST_TABLE: Override table name (default: watchlist)
    AWS_REGION: AWS region (default: us-east-1)
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def get_table_name() -> str:
    """Get the watchlist table name from environment."""
    if table := os.environ.get('WATCHLIST_TABLE'):
        return table
    return 'watchlist'


def get_dynamodb_table():
    """Get DynamoDB table resource."""
    region = os.environ.get('AWS_REGION', 'us-east-1')
    dynamodb = boto3.resource('dynamodb', region_name=region)
    return dynamodb.Table(get_table_name())


# Money market and cash symbols to exclude
CASH_SYMBOLS = {
    'CASH',  # Generic cash placeholder
    'SPAXX', 'FDRXX', 'FZFXX', 'FZDXX', 'FCASH', 'CORE',
    'SPRXX', 'FMPXX', 'FTEXX', 'FRGXX',
}
# Alias for backward compatibility
FIDELITY_CASH_SYMBOLS = CASH_SYMBOLS


def parse_fidelity_csv(filepath: str, include_cash: bool = False,
                       include_short: bool = True) -> list:
    """Parse Fidelity Portfolio Positions CSV export.

    Fidelity format:
    Account Number,Account Name,Symbol,Description,Quantity,Last Price,...,Type

    Args:
        filepath: Path to CSV file
        include_cash: Include money market/cash positions (default: False)
        include_short: Include short positions (default: True)

    Returns:
        List of deduplicated symbol records
    """
    symbols_seen = {}  # symbol -> record (dedup across accounts)

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError("CSV file has no headers")

        # Verify this looks like a Fidelity file
        required_cols = {'Symbol', 'Description'}
        actual_cols = set(reader.fieldnames)
        if not required_cols.issubset(actual_cols):
            raise ValueError(
                f"Not a Fidelity format. Expected columns: {required_cols}, "
                f"got: {actual_cols}"
            )

        for row in reader:
            symbol = (row.get('Symbol') or '').strip().upper()
            description = (row.get('Description') or '').strip()
            position_type = (row.get('Type') or '').strip()

            if not symbol:
                continue

            # Strip ** suffix from money market symbols
            symbol = symbol.rstrip('*')

            # Skip cash/money market unless requested
            if not include_cash:
                if symbol in FIDELITY_CASH_SYMBOLS:
                    continue
                if 'MONEY MARKET' in description.upper():
                    continue

            # Skip short positions unless requested
            if not include_short and position_type == 'Short':
                continue

            # Skip if already seen (dedup across accounts)
            if symbol in symbols_seen:
                continue

            # Determine symbol type from description
            symbol_type = 'equity'
            desc_upper = description.upper()

            # ETF detection keywords
            etf_keywords = [
                'ETF', 'SPDR', 'ISHARES', 'VANECK', 'INVESCO', 'PROSHARES',
                'WISDOMTREE', 'FIRST TRUST', 'GLOBAL X', 'DIREXION',
                'COMMODITY INDEX', 'GOLD TR', 'SILVER TR', 'SPROTT',
            ]
            if any(kw in desc_upper for kw in etf_keywords):
                symbol_type = 'etf'
            elif symbol.startswith('^'):
                # Only actual index symbols (like ^VIX, ^GSPC)
                symbol_type = 'index'
            elif 'TRUST' in desc_upper:
                # Trusts that hold commodities are typically ETFs
                if any(kw in desc_upper for kw in ['GOLD', 'SILVER', 'PLATINUM', 'PALLADIUM']):
                    symbol_type = 'etf'

            record = {
                'symbol': symbol,
                'symbol_type': symbol_type,
                'enabled': True,
                'priority': 100,
                'added_at': datetime.now(timezone.utc).isoformat(),
                'added_by': 'fidelity_import',
                'metadata': {
                    'name': description,
                    'source': 'fidelity',
                }
            }

            symbols_seen[symbol] = record

    return list(symbols_seen.values())


def parse_csv(filepath: str, symbol_column: str, type_column: str = None,
              name_column: str = None, priority_column: str = None) -> list:
    """Parse CSV file and return list of symbol records."""
    symbols = []

    with open(filepath, 'r', encoding='utf-8-sig') as f:  # utf-8-sig handles BOM from Excel
        # Try to detect delimiter
        sample = f.read(1024)
        f.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',\t;')
        except csv.Error:
            dialect = 'excel'  # Default to comma-separated

        reader = csv.DictReader(f, dialect=dialect)

        # Normalize column names (strip whitespace, lowercase for matching)
        if reader.fieldnames:
            field_map = {name.strip().lower(): name for name in reader.fieldnames}
        else:
            raise ValueError("CSV file has no headers")

        # Find the symbol column
        symbol_col_actual = None
        for col_name in [symbol_column, symbol_column.lower(), 'symbol', 'ticker', 'sym']:
            if col_name.lower() in field_map:
                symbol_col_actual = field_map[col_name.lower()]
                break

        if not symbol_col_actual:
            raise ValueError(f"Could not find symbol column. Available columns: {list(reader.fieldnames)}")

        # Find optional columns
        type_col_actual = None
        if type_column:
            if type_column.lower() in field_map:
                type_col_actual = field_map[type_column.lower()]
        else:
            for col_name in ['symbol_type', 'type', 'asset_type', 'category']:
                if col_name in field_map:
                    type_col_actual = field_map[col_name]
                    break

        name_col_actual = None
        if name_column:
            if name_column.lower() in field_map:
                name_col_actual = field_map[name_column.lower()]
        else:
            for col_name in ['name', 'description', 'company', 'title']:
                if col_name in field_map:
                    name_col_actual = field_map[col_name]
                    break

        priority_col_actual = None
        if priority_column:
            if priority_column.lower() in field_map:
                priority_col_actual = field_map[priority_column.lower()]
        else:
            for col_name in ['priority', 'rank', 'order']:
                if col_name in field_map:
                    priority_col_actual = field_map[col_name]
                    break

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            symbol = row.get(symbol_col_actual, '').strip().upper()

            if not symbol:
                continue  # Skip empty rows

            # Skip common non-symbol values
            if symbol in ('SYMBOL', 'TICKER', 'N/A', '-', ''):
                continue

            # Skip cash/money market symbols
            if symbol in CASH_SYMBOLS:
                continue

            record = {
                'symbol': symbol,
                'symbol_type': 'equity',  # Default
                'enabled': True,
                'priority': 100,  # Default priority
                'added_at': datetime.now(timezone.utc).isoformat(),
                'added_by': 'csv_import',
                'metadata': {}
            }

            # Get symbol type if available
            if type_col_actual and row.get(type_col_actual):
                type_val = row[type_col_actual].strip().lower()
                # Normalize common type values
                type_map = {
                    'etf': 'etf',
                    'stock': 'equity',
                    'equity': 'equity',
                    'index': 'index',
                    'idx': 'index',
                    'commodity': 'commodity',
                    'crypto': 'crypto',
                    'fund': 'etf',
                    'mutual fund': 'etf',
                }
                record['symbol_type'] = type_map.get(type_val, type_val)

            # Get name if available
            if name_col_actual and row.get(name_col_actual):
                record['metadata']['name'] = row[name_col_actual].strip()

            # Get priority if available
            if priority_col_actual and row.get(priority_col_actual):
                try:
                    record['priority'] = int(row[priority_col_actual])
                except ValueError:
                    pass  # Keep default priority

            symbols.append(record)

    return symbols


def import_symbols(table, symbols: list, dry_run: bool = False,
                   skip_existing: bool = True) -> tuple:
    """Import symbols to DynamoDB table."""
    added = 0
    skipped = 0
    errors = 0

    for record in symbols:
        symbol = record['symbol']

        try:
            if skip_existing:
                # Check if symbol already exists
                response = table.get_item(Key={'symbol': symbol})
                if 'Item' in response:
                    print(f"  SKIP: {symbol} (already exists)")
                    skipped += 1
                    continue

            if dry_run:
                print(f"  ADD:  {symbol} (type={record['symbol_type']}, priority={record['priority']})")
                added += 1
            else:
                table.put_item(Item=record)
                print(f"  ADD:  {symbol} (type={record['symbol_type']}, priority={record['priority']})")
                added += 1

        except ClientError as e:
            print(f"  ERROR: {symbol} - {e.response['Error']['Message']}")
            errors += 1

    return added, skipped, errors


def main():
    parser = argparse.ArgumentParser(
        description='Import symbols from CSV to watchlist DynamoDB table',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic import (auto-detect symbol column)
    python scripts/import_watchlist_csv.py ~/Downloads/symbols.csv

    # Preview without making changes
    python scripts/import_watchlist_csv.py symbols.csv --dry-run

    # Specify column names
    python scripts/import_watchlist_csv.py symbols.csv --symbol-column Ticker

    # Fidelity Portfolio Positions export
    python scripts/import_watchlist_csv.py ~/data/fidelity/Portfolio_Positions.csv --fidelity
    python scripts/import_watchlist_csv.py Portfolio_Positions.csv --fidelity --include-cash

    # Import to production
    ENVIRONMENT=prod AWS_REGION=us-east-1 python scripts/import_watchlist_csv.py symbols.csv
        """
    )
    parser.add_argument('csv_file', help='Path to CSV file')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without writing to DynamoDB')
    parser.add_argument('--symbol-column', default='symbol',
                        help='Name of the column containing symbols (default: auto-detect)')
    parser.add_argument('--type-column', default=None,
                        help='Name of the column containing symbol type (default: auto-detect)')
    parser.add_argument('--name-column', default=None,
                        help='Name of the column containing symbol name (default: auto-detect)')
    parser.add_argument('--priority-column', default=None,
                        help='Name of the column containing priority (default: auto-detect)')
    parser.add_argument('--replace-existing', action='store_true',
                        help='Replace existing symbols instead of skipping them')

    # Fidelity-specific options
    parser.add_argument('--fidelity', action='store_true',
                        help='Parse as Fidelity Portfolio Positions export')
    parser.add_argument('--include-cash', action='store_true',
                        help='Include money market/cash positions (Fidelity only)')
    parser.add_argument('--exclude-short', action='store_true',
                        help='Exclude short positions (Fidelity only)')

    args = parser.parse_args()

    # Validate CSV file exists
    if not os.path.exists(args.csv_file):
        print(f"Error: File not found: {args.csv_file}")
        sys.exit(1)

    # Parse CSV
    print(f"Reading CSV: {args.csv_file}")
    try:
        if args.fidelity:
            print("Using Fidelity format parser")
            symbols = parse_fidelity_csv(
                args.csv_file,
                include_cash=args.include_cash,
                include_short=not args.exclude_short
            )
        else:
            symbols = parse_csv(
                args.csv_file,
                args.symbol_column,
                args.type_column,
                args.name_column,
                args.priority_column
            )
    except Exception as e:
        print(f"Error parsing CSV: {e}")
        sys.exit(1)

    if not symbols:
        print("No symbols found in CSV file")
        sys.exit(1)

    print(f"Found {len(symbols)} symbols")

    # Show sample
    print("\nSample records:")
    for record in symbols[:5]:
        name = record['metadata'].get('name', '')
        print(f"  {record['symbol']:8} type={record['symbol_type']:8} priority={record['priority']:3} {name}")
    if len(symbols) > 5:
        print(f"  ... and {len(symbols) - 5} more")

    # Get table
    table_name = get_table_name()
    print(f"\nTarget table: {table_name}")
    print(f"AWS Region: {os.environ.get('AWS_REGION', 'us-east-1')}")

    if args.dry_run:
        print("\n** DRY RUN - no changes will be made **\n")

    # Confirm before import
    if not args.dry_run:
        response = input(f"\nImport {len(symbols)} symbols to {table_name}? [y/N] ")
        if response.lower() != 'y':
            print("Cancelled")
            sys.exit(0)

    # Import
    print("\nImporting symbols:")
    table = get_dynamodb_table()
    added, skipped, errors = import_symbols(
        table,
        symbols,
        dry_run=args.dry_run,
        skip_existing=not args.replace_existing
    )

    # Summary
    print("\nSummary:")
    print(f"  Added:   {added}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors:  {errors}")

    if args.dry_run:
        print("\n** DRY RUN - no changes were made **")
        print("Run without --dry-run to import symbols")


if __name__ == '__main__':
    main()
