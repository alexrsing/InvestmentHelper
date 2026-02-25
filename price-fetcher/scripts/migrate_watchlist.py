#!/usr/bin/env python3
"""
Migrate symbols to the new watchlist table.

This script:
1. Reads symbols from the legacy positions table (etf_monitoring_positions)
2. Adds them to the watchlist table
3. Adds market indices (^VIX, ^IXIC, ^GSPC, etc.)

Usage:
    python scripts/migrate_watchlist.py --dry-run  # Preview changes
    python scripts/migrate_watchlist.py            # Execute migration

Environment variables:
    ENVIRONMENT: Environment name (default: dev)
    AWS_REGION: AWS region (default: us-east-1)
    POSITIONS_TABLE: Legacy positions table name (default: etf_monitoring_positions)
    WATCHLIST_TABLE: Target watchlist table name (default: watchlist)
"""

import argparse
import os
import sys
from datetime import datetime

# Add project paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'fetchers'))

import boto3
from botocore.exceptions import ClientError

# Default indices to add
DEFAULT_INDICES = [
    {'symbol': '^VIX', 'symbol_type': 'index', 'priority': 10, 'metadata': {'name': 'CBOE Volatility Index', 'exchange': 'CBOE'}},
    {'symbol': '^GSPC', 'symbol_type': 'index', 'priority': 10, 'metadata': {'name': 'S&P 500', 'exchange': 'SNP'}},
    {'symbol': '^IXIC', 'symbol_type': 'index', 'priority': 10, 'metadata': {'name': 'NASDAQ Composite', 'exchange': 'NASDAQ'}},
    {'symbol': '^DJI', 'symbol_type': 'index', 'priority': 10, 'metadata': {'name': 'Dow Jones Industrial Average', 'exchange': 'DJI'}},
    {'symbol': '^RUT', 'symbol_type': 'index', 'priority': 10, 'metadata': {'name': 'Russell 2000', 'exchange': 'RUT'}},
]


def get_positions_symbols(dynamodb, positions_table: str) -> list[str]:
    """Read symbols from the legacy positions table."""
    try:
        table = dynamodb.Table(positions_table)
        items = []
        response = table.scan(ProjectionExpression='etf_symbol')
        items.extend(response.get('Items', []))

        while 'LastEvaluatedKey' in response:
            response = table.scan(
                ProjectionExpression='etf_symbol',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))

        symbols = [item['etf_symbol'] for item in items if 'etf_symbol' in item]
        return sorted(set(symbols))
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"Warning: Positions table '{positions_table}' not found")
            return []
        raise


def get_existing_watchlist_symbols(dynamodb, watchlist_table: str) -> set[str]:
    """Get symbols already in the watchlist table."""
    try:
        table = dynamodb.Table(watchlist_table)
        items = []
        response = table.scan(ProjectionExpression='symbol')
        items.extend(response.get('Items', []))

        while 'LastEvaluatedKey' in response:
            response = table.scan(
                ProjectionExpression='symbol',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))

        return {item['symbol'] for item in items if 'symbol' in item}
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"Warning: Watchlist table '{watchlist_table}' not found")
            return set()
        raise


def add_to_watchlist(
    dynamodb,
    watchlist_table: str,
    symbol: str,
    symbol_type: str = 'etf',
    priority: int = 100,
    added_by: str = 'migration',
    metadata: dict = None,
    dry_run: bool = False
) -> bool:
    """Add a symbol to the watchlist table."""
    item = {
        'symbol': symbol.upper(),
        'symbol_type': symbol_type,
        'enabled': True,
        'priority': priority,
        'added_at': datetime.now().isoformat(),
        'added_by': added_by,
    }
    if metadata:
        item['metadata'] = metadata

    if dry_run:
        print(f"  [DRY RUN] Would add: {symbol} ({symbol_type}, priority={priority})")
        return True

    try:
        table = dynamodb.Table(watchlist_table)
        table.put_item(Item=item)
        print(f"  Added: {symbol} ({symbol_type}, priority={priority})")
        return True
    except ClientError as e:
        print(f"  ERROR adding {symbol}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Migrate symbols to watchlist table')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing')
    parser.add_argument('--skip-indices', action='store_true', help='Skip adding default indices')
    parser.add_argument('--skip-positions', action='store_true', help='Skip migrating from positions table')
    args = parser.parse_args()

    # Configuration
    env = os.getenv('ENVIRONMENT', 'dev')
    region = os.getenv('AWS_REGION', 'us-east-1')
    positions_table = os.getenv('POSITIONS_TABLE', 'etf_monitoring_positions')
    watchlist_table = os.getenv('WATCHLIST_TABLE', 'watchlist')

    print(f"Environment: {env}")
    print(f"Region: {region}")
    print(f"Positions table: {positions_table}")
    print(f"Watchlist table: {watchlist_table}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Initialize DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name=region)

    # Get existing watchlist symbols
    print("Checking existing watchlist symbols...")
    existing_symbols = get_existing_watchlist_symbols(dynamodb, watchlist_table)
    print(f"  Found {len(existing_symbols)} existing symbols in watchlist")
    print()

    added_count = 0
    skipped_count = 0

    # Migrate from positions table
    if not args.skip_positions:
        print("Reading symbols from positions table...")
        positions_symbols = get_positions_symbols(dynamodb, positions_table)
        print(f"  Found {len(positions_symbols)} symbols in positions table")

        print("\nMigrating positions to watchlist...")
        for symbol in positions_symbols:
            if symbol in existing_symbols:
                print(f"  Skipped (exists): {symbol}")
                skipped_count += 1
                continue

            # Determine symbol type based on common ETF patterns
            if symbol.startswith('^'):
                symbol_type = 'index'
            else:
                symbol_type = 'etf'  # Default to ETF since source is etf_monitoring_positions

            if add_to_watchlist(
                dynamodb, watchlist_table, symbol,
                symbol_type=symbol_type,
                priority=50,  # Medium priority for migrated symbols
                added_by='migration',
                dry_run=args.dry_run
            ):
                added_count += 1
                existing_symbols.add(symbol)
        print()

    # Add default indices
    if not args.skip_indices:
        print("Adding default market indices...")
        for index_config in DEFAULT_INDICES:
            symbol = index_config['symbol']
            if symbol in existing_symbols:
                print(f"  Skipped (exists): {symbol}")
                skipped_count += 1
                continue

            if add_to_watchlist(
                dynamodb, watchlist_table, symbol,
                symbol_type=index_config['symbol_type'],
                priority=index_config['priority'],
                metadata=index_config.get('metadata'),
                added_by='migration',
                dry_run=args.dry_run
            ):
                added_count += 1
                existing_symbols.add(symbol)
        print()

    # Summary
    print("=" * 50)
    print("Migration Summary")
    print("=" * 50)
    print(f"  Symbols added: {added_count}")
    print(f"  Symbols skipped (already exist): {skipped_count}")
    print(f"  Total in watchlist: {len(existing_symbols)}")

    if args.dry_run:
        print("\n[DRY RUN] No changes were made. Run without --dry-run to execute migration.")


if __name__ == '__main__':
    main()
