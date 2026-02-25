"""
PriceData - DynamoDB price data client.

Installation:
    pip install git+https://github.com/sing-email/PriceData.git@v0.1.0

Read prices:
    from pricedata import get_price, get_price_history

    price = get_price("AAPL", date(2025, 12, 10))
    history = get_price_history("AAPL", date(2025, 1, 1), date(2025, 12, 31))

Check holidays:
    from pricedata import is_market_holiday, is_trading_day

    if is_market_holiday(date(2025, 12, 25)):
        print("Market closed for Christmas")

Write prices:
    from pricedata import store_price, store_price_history

    store_price("AAPL", date(2025, 12, 10), 150.25)
"""

from .client import (
    get_price,
    get_price_history,
    get_current_price,
    list_symbols,
    is_market_holiday,
    is_early_close,
    is_trading_day,
    get_market_holidays,
    load_holidays,
    store_price,
    store_price_history,
)

__version__ = "0.1.0"
__all__ = [
    "get_price",
    "get_price_history",
    "get_current_price",
    "list_symbols",
    "is_market_holiday",
    "is_early_close",
    "is_trading_day",
    "get_market_holidays",
    "load_holidays",
    "store_price",
    "store_price_history",
]
