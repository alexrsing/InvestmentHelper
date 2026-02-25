"""
Shared helpers for integration tests.

Provides DynamoDB table creation and other utilities for testing
with the new marketdata-{env}-{table} naming convention.
"""

import os
import sys


# Table names for tests (using test environment)
TEST_PRICES_TABLE = 'marketdata-test-prices'
TEST_WATCHLIST_TABLE = 'marketdata-test-watchlist'
TEST_CONFIG_TABLE = 'marketdata-test-config'


def setup_test_environment():
    """Set up environment variables for test table names."""
    os.environ['ENVIRONMENT'] = 'test'
    os.environ['PRICES_TABLE'] = TEST_PRICES_TABLE
    os.environ['WATCHLIST_TABLE'] = TEST_WATCHLIST_TABLE
    os.environ['CONFIG_TABLE_NAME'] = TEST_CONFIG_TABLE


def create_tables(dynamodb):
    """
    Create required DynamoDB tables for testing.

    Uses new marketdata-{env}-{table} naming convention.

    Args:
        dynamodb: boto3 DynamoDB resource

    Returns:
        Tuple of (watchlist_table, prices_table)
    """
    # Set up environment for table names
    setup_test_environment()

    # Create watchlist table (replaces legacy positions table)
    watchlist_table = dynamodb.create_table(
        TableName=TEST_WATCHLIST_TABLE,
        KeySchema=[{'AttributeName': 'symbol', 'KeyType': 'HASH'}],
        AttributeDefinitions=[
            {'AttributeName': 'symbol', 'AttributeType': 'S'},
            {'AttributeName': 'symbol_type', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'symbol_type-index',
                'KeySchema': [{'AttributeName': 'symbol_type', 'KeyType': 'HASH'}],
                'Projection': {'ProjectionType': 'ALL'}
            }
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # Create new marketdata-test-prices table
    prices_table = dynamodb.create_table(
        TableName=TEST_PRICES_TABLE,
        KeySchema=[{'AttributeName': 'etf_symbol', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'etf_symbol', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )

    # Wait for tables to be created
    watchlist_table.meta.client.get_waiter('table_exists').wait(TableName=TEST_WATCHLIST_TABLE)
    prices_table.meta.client.get_waiter('table_exists').wait(TableName=TEST_PRICES_TABLE)

    return watchlist_table, prices_table


def create_all_tables(dynamodb):
    """
    Create all DynamoDB tables including config table.

    Args:
        dynamodb: boto3 DynamoDB resource

    Returns:
        Tuple of (watchlist_table, prices_table, config_table)
    """
    watchlist_table, prices_table = create_tables(dynamodb)

    # Create new marketdata-test-config table
    config_table = dynamodb.create_table(
        TableName=TEST_CONFIG_TABLE,
        KeySchema=[
            {'AttributeName': 'config_type', 'KeyType': 'HASH'},
            {'AttributeName': 'config_key', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'config_type', 'AttributeType': 'S'},
            {'AttributeName': 'config_key', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    config_table.meta.client.get_waiter('table_exists').wait(TableName=TEST_CONFIG_TABLE)

    return watchlist_table, prices_table, config_table


def add_watchlist_symbol(table, symbol: str, symbol_type: str = 'etf', enabled: bool = True, priority: int = 100):
    """
    Add a symbol to the watchlist table for testing.

    Args:
        table: DynamoDB table resource for watchlist
        symbol: Symbol to add
        symbol_type: Type of symbol ('etf', 'index', etc.)
        enabled: Whether symbol is enabled
        priority: Fetch priority
    """
    from datetime import datetime
    table.put_item(Item={
        'symbol': symbol,
        'symbol_type': symbol_type,
        'enabled': enabled,
        'priority': priority,
        'added_at': datetime.now().isoformat(),
        'added_by': 'test'
    })


def clear_module_caches(extra_modules=None):
    """
    Clear module caches to ensure fresh imports.

    Args:
        extra_modules: Additional module name patterns to clear
    """
    patterns = ['lambda_handler', 'main', 'db_service', 'api_keys', 'pricedata', 'config_service']
    if extra_modules:
        patterns.extend(extra_modules)

    for mod_name in list(sys.modules.keys()):
        if any(x in mod_name for x in patterns):
            del sys.modules[mod_name]
