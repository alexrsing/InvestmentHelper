from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, UTCDateTimeAttribute
from datetime import datetime, timezone


class ETFResearch(Model):
    class Meta:
        table_name = "etf_research"
        region = "us-east-1"

    user_id = UnicodeAttribute(hash_key=True)
    ticker = UnicodeAttribute(range_key=True)
    sentiment = UnicodeAttribute()  # "Bullish", "Bearish", "Neutral"
    summary = UnicodeAttribute()
    signal_at_research = UnicodeAttribute()  # "Buy" or "Sell"
    researched_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
