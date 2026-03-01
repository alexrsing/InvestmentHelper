from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, NumberAttribute, UTCDateTimeAttribute
from datetime import datetime, timezone


class TradeDecision(Model):
    class Meta:
        table_name = "trade_decisions"
        region = "us-east-1"

    user_id = UnicodeAttribute(hash_key=True)
    decision_key = UnicodeAttribute(range_key=True)  # {YYYY-MM-DD}#{TICKER}

    date = UnicodeAttribute()
    ticker = UnicodeAttribute()
    signal = UnicodeAttribute()  # Buy / Sell
    action = UnicodeAttribute()  # accepted / declined
    shares = NumberAttribute()
    price = NumberAttribute()
    position_before = NumberAttribute()
    position_after = NumberAttribute()
    cash_before = NumberAttribute()
    cash_after = NumberAttribute()
    created_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
