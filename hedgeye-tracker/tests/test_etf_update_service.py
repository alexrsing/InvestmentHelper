"""Tests for ETFUpdateService - verifies partial updates on shared etfs and etf_history tables."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from moto import mock_aws
from decimal import Decimal


class TestETFUpdateService:
    """Test ETFUpdateService partial update behavior."""

    def _make_trade_range(self, ticker, low, high, all_history=None):
        """Helper to create a trade range dict."""
        return {
            "etf_symbol": ticker,
            "current_data": {
                "trade_low": str(low),
                "trade_high": str(high),
                "trend": "BULLISH",
            },
            "all_history": all_history if all_history is not None else [],
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


class TestUpdateHistoryRiskRanges:
    """Test ETFUpdateService.update_history_risk_ranges() partial update behavior."""

    def _create_etf_history_table(self, dynamodb):
        """Helper to create the etf_history table."""
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
        return table

    @mock_aws
    def test_updates_risk_ranges_on_existing_history_record(self):
        """Updates risk_range_low/high on an existing etf_history record, preserving other fields."""
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = self._create_etf_history_table(dynamodb)

        # Pre-populate with an etf_history record (as price-fetcher would)
        table.put_item(Item={
            "ticker": "SPY",
            "date": "2025-10-15",
            "open_price": Decimal("448.50"),
            "close_price": Decimal("450.00"),
            "high_price": Decimal("451.00"),
            "low_price": Decimal("447.00"),
            "volume": Decimal("50000000"),
        })

        from services.etf_update_service import ETFUpdateService
        service = ETFUpdateService()

        trade_ranges = [{
            "etf_symbol": "SPY",
            "current_data": {"trade_low": "445.0", "trade_high": "455.0"},
            "all_history": [
                {"timestamp": "2025-10-15T07:43:03-04:00", "range": [Decimal("445.0"), Decimal("455.0")]},
            ],
        }]
        count = service.update_history_risk_ranges(trade_ranges)

        assert count == 1

        # Verify risk ranges were set
        response = table.get_item(Key={"ticker": "SPY", "date": "2025-10-15"})
        item = response["Item"]
        assert float(item["risk_range_low"]) == 445.0
        assert float(item["risk_range_high"]) == 455.0

        # Verify OHLCV fields were preserved
        assert float(item["open_price"]) == 448.50
        assert float(item["close_price"]) == 450.00
        assert float(item["volume"]) == 50000000

    @mock_aws
    def test_skips_dates_without_history_record(self):
        """Skips dates where no etf_history record exists (doesn't crash)."""
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        self._create_etf_history_table(dynamodb)

        from services.etf_update_service import ETFUpdateService
        service = ETFUpdateService()

        trade_ranges = [{
            "etf_symbol": "SPY",
            "current_data": {"trade_low": "445.0", "trade_high": "455.0"},
            "all_history": [
                {"timestamp": "2025-10-15T07:43:03-04:00", "range": [Decimal("445.0"), Decimal("455.0")]},
            ],
        }]
        count = service.update_history_risk_ranges(trade_ranges)

        assert count == 0

    @mock_aws
    def test_returns_correct_count_across_multiple_tickers(self):
        """Returns correct count when updating multiple tickers and dates."""
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = self._create_etf_history_table(dynamodb)

        # Add history records for two tickers
        table.put_item(Item={"ticker": "SPY", "date": "2025-10-15"})
        table.put_item(Item={"ticker": "SPY", "date": "2025-10-14"})
        table.put_item(Item={"ticker": "QQQ", "date": "2025-10-15"})

        from services.etf_update_service import ETFUpdateService
        service = ETFUpdateService()

        trade_ranges = [
            {
                "etf_symbol": "SPY",
                "current_data": {"trade_low": "445.0", "trade_high": "455.0"},
                "all_history": [
                    {"timestamp": "2025-10-15T07:43:03-04:00", "range": [Decimal("445.0"), Decimal("455.0")]},
                    {"timestamp": "2025-10-14T07:43:03-04:00", "range": [Decimal("444.0"), Decimal("454.0")]},
                    {"timestamp": "2025-10-13T07:43:03-04:00", "range": [Decimal("443.0"), Decimal("453.0")]},  # No record
                ],
            },
            {
                "etf_symbol": "QQQ",
                "current_data": {"trade_low": "375.0", "trade_high": "385.0"},
                "all_history": [
                    {"timestamp": "2025-10-15T07:43:03-04:00", "range": [Decimal("375.0"), Decimal("385.0")]},
                ],
            },
        ]
        count = service.update_history_risk_ranges(trade_ranges)

        # SPY: 2 dates matched, 1 skipped. QQQ: 1 date matched.
        assert count == 3
