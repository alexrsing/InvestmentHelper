from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute,
    NumberAttribute,
    UTCDateTimeAttribute,
)
from datetime import datetime, timezone


DEFAULT_MAX_POSITION_PCT = 2.5
DEFAULT_MIN_POSITION_PCT = 0.0


class TradingRules(Model):
    class Meta:
        table_name = "trading_rules"
        region = "us-east-1"

    user_id = UnicodeAttribute(hash_key=True)
    max_position_pct = NumberAttribute(default=DEFAULT_MAX_POSITION_PCT)
    min_position_pct = NumberAttribute(default=DEFAULT_MIN_POSITION_PCT)
    created_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
    updated_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
