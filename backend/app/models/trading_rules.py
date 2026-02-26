from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute,
    NumberAttribute,
    UTCDateTimeAttribute,
)
from datetime import datetime, timezone


class TradingRules(Model):
    class Meta:
        table_name = "trading_rules"
        region = "us-east-1"

    user_id = UnicodeAttribute(hash_key=True)
    max_position_pct = NumberAttribute(default=2.5)
    created_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
    updated_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
