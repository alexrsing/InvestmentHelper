from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, NumberAttribute, UTCDateTimeAttribute
from datetime import datetime, timezone
import os


class ETF(Model):
    class Meta:
        table_name = "etfs"
        region = "us-east-1"
        host = os.getenv("DYNAMODB_ENDPOINT") or None

    ticker = UnicodeAttribute(hash_key=True)
    name = UnicodeAttribute(null=True)
    description = UnicodeAttribute(null=True)
    expense_ratio = NumberAttribute(null=True)
    aum = NumberAttribute(null=True)
    inception_date = UTCDateTimeAttribute(null=True)
    current_price = NumberAttribute(null=True)
    open_price = NumberAttribute(null=True)
    risk_range_low = NumberAttribute(null=True)
    risk_range_high = NumberAttribute(null=True)
    created_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
    updated_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))


class ETFHistory(Model):
    class Meta:
        table_name = "etf_history"
        region = "us-east-1"
        host = os.getenv("DYNAMODB_ENDPOINT") or None

    ticker = UnicodeAttribute(hash_key=True)
    date = UnicodeAttribute(range_key=True)
    open_price = NumberAttribute()
    high_price = NumberAttribute()
    low_price = NumberAttribute()
    close_price = NumberAttribute()
    adjusted_close = NumberAttribute(null=True)
    volume = NumberAttribute()
    risk_range_low = NumberAttribute(null=True)
    risk_range_high = NumberAttribute(null=True)
    created_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
