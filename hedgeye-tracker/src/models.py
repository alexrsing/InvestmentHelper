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
    current_price = NumberAttribute(null=True)
    open_price = NumberAttribute(null=True)
    risk_range_low = NumberAttribute(null=True)
    risk_range_high = NumberAttribute(null=True)
    created_at = UTCDateTimeAttribute(null=True)
    updated_at = UTCDateTimeAttribute(null=True)


class ETFHistory(Model):
    class Meta:
        table_name = "etf_history"
        region = "us-east-1"
        host = os.getenv("DYNAMODB_ENDPOINT") or None

    ticker = UnicodeAttribute(hash_key=True)
    date = UnicodeAttribute(range_key=True)
    risk_range_low = NumberAttribute(null=True)
    risk_range_high = NumberAttribute(null=True)
