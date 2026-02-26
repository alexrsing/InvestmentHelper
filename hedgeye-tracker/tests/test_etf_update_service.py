"""Tests for ETFUpdateService - verifies partial updates on shared etfs table."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from moto import mock_aws
from decimal import Decimal


class TestETFUpdateService:
    """Test ETFUpdateService partial update behavior."""

    def _make_trade_range(self, ticker, low, high):
        """Helper to create a trade range dict."""
        return {
            "etf_symbol": ticker,
            "current_data": {
                "trade_low": str(low),
                "trade_high": str(high),
                "trend": "BULLISH",
            },
            "all_history": [],
        }

    @mock_aws
    def test_updates_risk_ranges_on_existing_etf(self):
        """Updates risk_range_low and risk_range_high on an existing ETF record."""
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        # Create table
        table = dynamodb.create_table(
            TableName="etfs",
            KeySchema=[{"AttributeName": "ticker", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "ticker", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()

        # Pre-populate with an ETF record (as price-fetcher would)
        table.put_item(Item={
            "ticker": "SPY",
            "name": "SPDR S&P 500 ETF",
            "current_price": Decimal("450.00"),
            "open_price": Decimal("448.50"),
        })

        from services.etf_update_service import ETFUpdateService
        service = ETFUpdateService()

        trade_ranges = [self._make_trade_range("SPY", 445.0, 455.0)]
        count = service.update_risk_ranges(trade_ranges)

        assert count == 1

        # Verify the risk ranges were set
        response = table.get_item(Key={"ticker": "SPY"})
        item = response["Item"]
        assert float(item["risk_range_low"]) == 445.0
        assert float(item["risk_range_high"]) == 455.0

    @mock_aws
    def test_does_not_overwrite_price_fields(self):
        """Partial update preserves current_price, open_price, and name."""
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        table = dynamodb.create_table(
            TableName="etfs",
            KeySchema=[{"AttributeName": "ticker", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "ticker", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()

        table.put_item(Item={
            "ticker": "QQQ",
            "name": "Invesco QQQ Trust",
            "current_price": Decimal("380.00"),
            "open_price": Decimal("378.00"),
        })

        from services.etf_update_service import ETFUpdateService
        service = ETFUpdateService()

        trade_ranges = [self._make_trade_range("QQQ", 375.0, 385.0)]
        service.update_risk_ranges(trade_ranges)

        response = table.get_item(Key={"ticker": "QQQ"})
        item = response["Item"]

        # Price fields should be untouched
        assert float(item["current_price"]) == 380.00
        assert float(item["open_price"]) == 378.00
        assert item["name"] == "Invesco QQQ Trust"

        # Risk ranges should be updated
        assert float(item["risk_range_low"]) == 375.0
        assert float(item["risk_range_high"]) == 385.0

    @mock_aws
    def test_skips_nonexistent_ticker(self):
        """Logs warning and skips when ticker doesn't exist in etfs table."""
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        table = dynamodb.create_table(
            TableName="etfs",
            KeySchema=[{"AttributeName": "ticker", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "ticker", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()

        from services.etf_update_service import ETFUpdateService
        service = ETFUpdateService()

        trade_ranges = [self._make_trade_range("NONEXISTENT", 100.0, 110.0)]
        count = service.update_risk_ranges(trade_ranges)

        assert count == 0

    @mock_aws
    def test_handles_invalid_numeric_values(self):
        """Skips records with invalid or non-positive numeric values."""
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        table = dynamodb.create_table(
            TableName="etfs",
            KeySchema=[{"AttributeName": "ticker", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "ticker", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()

        table.put_item(Item={"ticker": "SPY", "current_price": Decimal("450.00")})

        from services.etf_update_service import ETFUpdateService
        service = ETFUpdateService()

        # Invalid: non-numeric
        trade_ranges = [{
            "etf_symbol": "SPY",
            "current_data": {"trade_low": "abc", "trade_high": "def"},
            "all_history": [],
        }]
        count = service.update_risk_ranges(trade_ranges)
        assert count == 0

        # Invalid: zero values
        trade_ranges = [self._make_trade_range("SPY", 0, 0)]
        count = service.update_risk_ranges(trade_ranges)
        assert count == 0

    @mock_aws
    def test_returns_correct_count(self):
        """Returns the count of successfully updated records."""
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        table = dynamodb.create_table(
            TableName="etfs",
            KeySchema=[{"AttributeName": "ticker", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "ticker", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()

        # Add 2 ETFs
        table.put_item(Item={"ticker": "SPY", "current_price": Decimal("450.00")})
        table.put_item(Item={"ticker": "QQQ", "current_price": Decimal("380.00")})

        from services.etf_update_service import ETFUpdateService
        service = ETFUpdateService()

        trade_ranges = [
            self._make_trade_range("SPY", 445.0, 455.0),
            self._make_trade_range("QQQ", 375.0, 385.0),
            self._make_trade_range("NONEXISTENT", 100.0, 110.0),  # Should be skipped
        ]
        count = service.update_risk_ranges(trade_ranges)

        assert count == 2
