"""Shared test fixtures for hedgeye-tracker tests."""

import os
import sys
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Set test environment variables before any imports that use them
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")

from moto import mock_aws

@pytest.fixture
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def dynamodb_table(aws_credentials):
    """Create a mocked etfs DynamoDB table."""
    with mock_aws():
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        # Create the etfs table matching the PynamoDB model schema
        table = dynamodb.create_table(
            TableName="etfs",
            KeySchema=[{"AttributeName": "ticker", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "ticker", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()

        yield dynamodb


@pytest.fixture
def etf_history_table(aws_credentials):
    """Create a mocked etf_history DynamoDB table."""
    with mock_aws():
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        table = dynamodb.create_table(
            TableName="etf_history",
            KeySchema=[
                {"AttributeName": "ticker", "KeyType": "HASH"},
                {"AttributeName": "date", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "ticker", "AttributeType": "S"},
                {"AttributeName": "date", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()

        yield dynamodb


@pytest.fixture
def etfs_table_with_data(dynamodb_table):
    """Create etfs table with sample ETF records."""
    table = dynamodb_table.Table("etfs")

    # Add sample ETF records (as created by price-fetcher)
    sample_etfs = [
        {"ticker": "SPY", "name": "SPDR S&P 500 ETF", "current_price": "450.00", "open_price": "448.50"},
        {"ticker": "QQQ", "name": "Invesco QQQ Trust", "current_price": "380.00", "open_price": "378.00"},
        {"ticker": "IWM", "name": "iShares Russell 2000 ETF", "current_price": "200.00", "open_price": "199.00"},
    ]

    for etf in sample_etfs:
        table.put_item(Item=etf)

    yield dynamodb_table
