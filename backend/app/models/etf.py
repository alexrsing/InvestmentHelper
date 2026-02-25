from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute,
    NumberAttribute,
    UTCDateTimeAttribute,
    MapAttribute
)
from datetime import datetime, timezone


class ETF(Model):
    """
    ETF model for DynamoDB
    Stores ETF information
    """
    class Meta:
        table_name = "etfs"
        region = "us-east-1"  # Update with your AWS region

    # Primary key
    ticker = UnicodeAttribute(hash_key=True)

    # ETF attributes
    name = UnicodeAttribute(null=True)
    description = UnicodeAttribute(null=True)
    expense_ratio = NumberAttribute(null=True)
    aum = NumberAttribute(null=True)  # Assets Under Management
    inception_date = UTCDateTimeAttribute(null=True)
    current_price = NumberAttribute(null=True)
    open_price = NumberAttribute(null=True)
    risk_range_low = NumberAttribute(null=True)
    risk_range_high = NumberAttribute(null=True)

    # Metadata
    created_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
    updated_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<ETF(ticker='{self.ticker}', name='{self.name}')>"


class ETFHistoryItem(MapAttribute):
    """
    Map attribute for storing individual history records
    """
    date = UTCDateTimeAttribute()
    open_price = NumberAttribute()
    high_price = NumberAttribute()
    low_price = NumberAttribute()
    close_price = NumberAttribute()
    adjusted_close = NumberAttribute(null=True)
    volume = NumberAttribute()


class ETFHistory(Model):
    """
    ETF History model for DynamoDB
    Stores historical price data for ETFs
    """
    class Meta:
        table_name = "etf_history"
        region = "us-east-1"  # Update with your AWS region

    # Composite key: ticker (hash key) + date (range key)
    ticker = UnicodeAttribute(hash_key=True)
    date = UnicodeAttribute(range_key=True)  # Store as ISO format string for sorting

    # Price data
    open_price = NumberAttribute()
    high_price = NumberAttribute()
    low_price = NumberAttribute()
    close_price = NumberAttribute()
    adjusted_close = NumberAttribute(null=True)
    volume = NumberAttribute()
    risk_range_low = NumberAttribute(null=True)
    risk_range_high = NumberAttribute(null=True)

    # Metadata
    created_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<ETFHistory(ticker='{self.ticker}', date='{self.date}', close={self.close_price})>"