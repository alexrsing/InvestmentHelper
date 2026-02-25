#!/usr/bin/env python3
"""
Migrate market holidays from local JSON file to DynamoDB config table.

This is a one-time migration script to move holiday data from the
filesystem to DynamoDB for Lambda compatibility.

Usage:
    python scripts/migrate_holidays_to_dynamodb.py [--dry-run]

Environment variables:
    CONFIG_TABLE_NAME: DynamoDB table name (default: price_fetcher_config)
    AWS_REGION: AWS region (default: us-east-1)
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project paths for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'fetchers'))

from logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def get_holidays_file_path() -> Path:
    """Get path to the holidays JSON file."""
    return project_root / 'config' / 'market_holidays.json'


def load_holidays_from_file(file_path: Path) -> dict:
    """Load holidays data from JSON file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Holidays file not found: {file_path}")

    with open(file_path) as f:
        data = json.load(f)

    logger.info(
        "Loaded holidays from file",
        extra={
            'path': str(file_path),
            'exchange': data.get('exchange'),
            'holiday_count': len(data.get('holidays', []))
        }
    )
    return data


def migrate_holidays(dry_run: bool = False) -> bool:
    """
    Migrate holidays from JSON file to DynamoDB.

    Args:
        dry_run: If True, only show what would be migrated

    Returns:
        True if successful
    """
    # Load from file
    file_path = get_holidays_file_path()

    try:
        holidays_data = load_holidays_from_file(file_path)
    except FileNotFoundError:
        # Try sample file if main file doesn't exist
        sample_path = file_path.with_suffix('.sample.json')
        if sample_path.exists():
            logger.info("Using sample holidays file")
            holidays_data = load_holidays_from_file(sample_path)
        else:
            logger.error("No holidays file found")
            return False

    exchange = holidays_data.get('exchange', 'US')
    holiday_count = len(holidays_data.get('holidays', []))

    if dry_run:
        logger.info(
            "DRY RUN: Would migrate %d holidays for exchange %s",
            holiday_count, exchange
        )
        logger.info("Holiday data preview:")
        for holiday in holidays_data.get('holidays', [])[:5]:
            logger.info("  %s: %s", holiday.get('atDate'), holiday.get('eventName'))
        if holiday_count > 5:
            logger.info("  ... and %d more", holiday_count - 5)
        return True

    # Store in DynamoDB
    from config_service import get_config_service

    config = get_config_service()
    config.put_config(
        config_type='holidays',
        config_key=exchange,
        data=holidays_data
    )

    logger.info(
        "Successfully migrated holidays to DynamoDB",
        extra={
            'exchange': exchange,
            'holiday_count': holiday_count,
            'table': config.table_name
        }
    )

    return True


def verify_migration(exchange: str = 'US') -> bool:
    """
    Verify that holidays were migrated successfully.

    Args:
        exchange: Exchange code to verify

    Returns:
        True if verification passed
    """
    from config_service import get_config_service

    config = get_config_service()
    data = config.get_config('holidays', exchange)

    if not data:
        logger.error("Verification failed: no data found in DynamoDB")
        return False

    holiday_count = len(data.get('holidays', []))
    logger.info(
        "Verification passed",
        extra={
            'exchange': exchange,
            'holiday_count': holiday_count
        }
    )
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Migrate market holidays to DynamoDB'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without making changes'
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify existing migration, do not migrate'
    )
    parser.add_argument(
        '--exchange',
        default='US',
        help='Exchange code (default: US)'
    )

    args = parser.parse_args()

    if args.verify_only:
        success = verify_migration(args.exchange)
    else:
        success = migrate_holidays(dry_run=args.dry_run)
        if success and not args.dry_run:
            success = verify_migration(args.exchange)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
