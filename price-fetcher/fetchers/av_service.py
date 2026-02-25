import time
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from threading import Lock

from logging_config import get_logger
from rate_limit import get_service_rate_config, calculate_backoff, should_retry

logger = get_logger(__name__)


class AlphaVantageService:
    """
    Alpha Vantage API service with configurable rate limiting.

    Free tier: 25 requests/day, 5 requests/minute
    Paid tiers have higher limits - configure via environment variables.
    """

    BASE_URL = "https://www.alphavantage.co/query"

    # Rate limit presets
    # Free tier: 25/day, but also limited to ~1 request per second burst
    TIER_LIMITS = {
        "free": {"per_minute": 5, "per_day": 25, "intraday": False},
        "paid_30": {"per_minute": 30, "per_day": None, "intraday": True},
        "paid_75": {"per_minute": 75, "per_day": None, "intraday": True},
        "paid_150": {"per_minute": 150, "per_day": None, "intraday": True},
        "paid_300": {"per_minute": 300, "per_day": None, "intraday": True},
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        tier: str = "free",
        max_retries: Optional[int] = None
    ):
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("Alpha Vantage API key required. Set ALPHA_VANTAGE_API_KEY environment variable.")

        # Use centralized rate limit config (tier from env var or parameter)
        self._rate_config = get_service_rate_config('alphavantage')
        self.tier = self._rate_config.get('tier', tier.lower())
        self.max_retries = max_retries if max_retries is not None else self._rate_config['max_retries']

        # Get rate limits from centralized config (fallback to local TIER_LIMITS)
        limits = self.TIER_LIMITS.get(self.tier, self.TIER_LIMITS["free"])
        self.requests_per_minute = self._rate_config.get('per_minute') or limits["per_minute"]
        self.requests_per_day = self._rate_config.get('per_day')
        self.supports_intraday = limits.get("intraday", False)

        # Minimum delay from centralized config
        self._min_delay = self._rate_config.get('min_delay', 2.0 if self.tier == "free" else 0.5)

        # Request tracking for rate limiting
        self._request_times: List[datetime] = []
        self._daily_count = 0
        self._daily_reset = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        self._lock = Lock()
        self._last_request_time: Optional[datetime] = None

    def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limits."""
        with self._lock:
            now = datetime.now()

            # Reset daily counter if new day
            if now >= self._daily_reset:
                self._daily_count = 0
                self._daily_reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

            # Check daily limit
            if self.requests_per_day and self._daily_count >= self.requests_per_day:
                raise Exception(f"Daily rate limit ({self.requests_per_day}) exceeded. Resets at midnight.")

            # Enforce minimum delay between requests (burst limit)
            if self._last_request_time:
                elapsed = (now - self._last_request_time).total_seconds()
                if elapsed < self._min_delay:
                    sleep_time = self._min_delay - elapsed
                    time.sleep(sleep_time)
                    now = datetime.now()

            # Clean old request times (older than 1 minute)
            one_minute_ago = now - timedelta(minutes=1)
            self._request_times = [t for t in self._request_times if t > one_minute_ago]

            # Wait if at per-minute limit
            if len(self._request_times) >= self.requests_per_minute:
                oldest = min(self._request_times)
                wait_time = (oldest + timedelta(minutes=1) - now).total_seconds()
                if wait_time > 0:
                    logger.debug("Rate limit: waiting %.1fs", wait_time)
                    time.sleep(wait_time + 0.1)
                    now = datetime.now()
                    one_minute_ago = now - timedelta(minutes=1)
                    self._request_times = [t for t in self._request_times if t > one_minute_ago]

            self._last_request_time = now

            # Record this request
            self._request_times.append(now)
            self._daily_count += 1

    def _make_request(self, params: Dict[str, str]) -> Dict[str, Any]:
        """Make an API request with rate limiting and retry logic."""
        params["apikey"] = self.api_key

        last_error = None
        for attempt in range(self.max_retries):
            try:
                self._wait_for_rate_limit()

                response = requests.get(self.BASE_URL, params=params, timeout=30)

                # Handle forbidden - symbol not available or API access issue
                if response.status_code == 403:
                    return None  # Symbol not available, don't retry

                response.raise_for_status()

                data = response.json()

                # Check for API error messages
                if "Error Message" in data:
                    raise Exception(f"API error: {data['Error Message']}")
                if "Note" in data and "rate limit" in data["Note"].lower():
                    # Hit rate limit despite our tracking - wait and retry
                    if not should_retry(attempt, self._rate_config):
                        logger.warning("API rate limit hit. Max retries reached, failing fast.")
                        return None
                    wait_time = calculate_backoff(attempt, self._rate_config)
                    logger.warning(
                        "API rate limit hit. Waiting %.1fs (retry %d/%d)",
                        wait_time, attempt + 1, self.max_retries
                    )
                    time.sleep(wait_time)
                    continue
                if "Information" in data:
                    # Usually indicates rate limit or invalid request
                    raise Exception(f"API info: {data['Information']}")

                return data

            except requests.exceptions.RequestException as e:
                last_error = e
                if not should_retry(attempt, self._rate_config):
                    logger.warning("Request error: %s. Max retries reached.", e)
                    break
                wait_time = calculate_backoff(attempt, self._rate_config)
                logger.warning(
                    "Request error: %s. Waiting %.1fs (retry %d/%d)",
                    e, wait_time, attempt + 1, self.max_retries
                )
                time.sleep(wait_time)
            except Exception as e:
                last_error = e
                if "rate limit" in str(e).lower():
                    if not should_retry(attempt, self._rate_config):
                        logger.warning("%s. Max retries reached, failing fast.", e)
                        return None
                    wait_time = calculate_backoff(attempt, self._rate_config)
                    logger.warning(
                        "%s. Waiting %.1fs (retry %d/%d)",
                        e, wait_time, attempt + 1, self.max_retries
                    )
                    time.sleep(wait_time)
                else:
                    raise

        raise Exception(f"Max retries exceeded: {last_error}")

    def get_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current quote information for a symbol.
        Returns dict with current_price, change_percent, volume, etc.
        """
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "datatype": "json"
        }

        data = self._make_request(params)
        quote = data.get("Global Quote", {})

        if not quote:
            return None

        # Map Alpha Vantage fields to our format (matching yfinance structure)
        return {
            "regularMarketPrice": float(quote.get("05. price", 0)),
            "regularMarketChangePercent": float(quote.get("10. change percent", "0").rstrip("%")),
            "volume": int(quote.get("06. volume", 0)),
            "regularMarketOpen": float(quote.get("02. open", 0)),
            "regularMarketDayHigh": float(quote.get("03. high", 0)),
            "regularMarketDayLow": float(quote.get("04. low", 0)),
            "regularMarketPreviousClose": float(quote.get("08. previous close", 0)),
            "symbol": quote.get("01. symbol", symbol)
        }

    def get_historical_data(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get historical price data for a symbol.

        Args:
            symbol: Stock/ETF symbol
            period: Time period - '1d', '5d', '1mo' (used to limit results)
            interval: Data interval - '5m', '15m', '1d'

        Returns:
            List of dicts with 'date' and 'close' keys
        """
        # Check if intraday is supported on this tier
        is_intraday = interval in ("5m", "5min", "15m", "15min")
        if is_intraday and not self.supports_intraday:
            # Intraday data requires premium subscription
            return None

        # Map interval to Alpha Vantage function and interval parameter
        if interval in ("5m", "5min"):
            function = "TIME_SERIES_INTRADAY"
            av_interval = "5min"
        elif interval in ("15m", "15min"):
            function = "TIME_SERIES_INTRADAY"
            av_interval = "15min"
        elif interval in ("1d", "daily"):
            function = "TIME_SERIES_DAILY"
            av_interval = None
        else:
            raise ValueError(f"Unsupported interval: {interval}")

        params = {
            "function": function,
            "symbol": symbol,
            "datatype": "json",
            "outputsize": "compact"  # Last 100 data points
        }

        if av_interval:
            params["interval"] = av_interval

        data = self._make_request(params)

        # Find the time series data in response
        time_series_key = None
        for key in data.keys():
            if "Time Series" in key:
                time_series_key = key
                break

        if not time_series_key:
            return None

        time_series = data[time_series_key]

        # Convert to our format (full OHLCV)
        result = []
        for date_str, values in time_series.items():
            result.append({
                "date": date_str,
                "open": float(values.get("1. open", 0)),
                "high": float(values.get("2. high", 0)),
                "low": float(values.get("3. low", 0)),
                "close": float(values.get("4. close", 0)),
                "volume": int(values.get("5. volume", 0)),
                "adjusted_close": None,
            })

        # Sort by date ascending
        result.sort(key=lambda x: x["date"])

        # Filter by period
        if period == "1d":
            # Keep only last day's data
            if result:
                last_date = result[-1]["date"].split()[0] if " " in result[-1]["date"] else result[-1]["date"]
                result = [r for r in result if r["date"].startswith(last_date)]
        elif period == "5d":
            # Keep only last 5 days
            cutoff = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
            result = [r for r in result if r["date"] >= cutoff]
        # For '1mo', keep all (compact output is ~100 points anyway)

        return result if result else None

    def get_remaining_requests(self) -> Dict[str, Any]:
        """Get information about remaining rate limit quota."""
        with self._lock:
            now = datetime.now()
            one_minute_ago = now - timedelta(minutes=1)
            recent_requests = len([t for t in self._request_times if t > one_minute_ago])

            return {
                "requests_this_minute": recent_requests,
                "remaining_this_minute": self.requests_per_minute - recent_requests,
                "requests_today": self._daily_count,
                "remaining_today": (self.requests_per_day - self._daily_count) if self.requests_per_day else "unlimited",
                "tier": self.tier
            }
