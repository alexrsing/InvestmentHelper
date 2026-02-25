from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute,
    NumberAttribute,
    UTCDateTimeAttribute,
    ListAttribute,
    MapAttribute,
)
from datetime import datetime, timezone


class HoldingMap(MapAttribute):
    ticker = UnicodeAttribute()
    shares = NumberAttribute()
    cost_basis = NumberAttribute()


class Portfolio(Model):
    class Meta:
        table_name = "portfolios"
        region = "us-east-1"

    user_id = UnicodeAttribute(hash_key=True)
    initial_value = NumberAttribute(default=0)
    holdings = ListAttribute(of=HoldingMap, default=list)
    created_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
    updated_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
