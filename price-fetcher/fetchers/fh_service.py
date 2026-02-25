import time
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from threading import Lock

from logging_config import get_logger
from rate_limit import get_service_rate_config, calculate_backoff, should_retry

logger = get_logger(__name__)


class FinnhubService:
    """
    Finnhub API service with configurable rate limiting.

    Free tier: 60 API calls/minute
    Paid tiers have higher limits.
    """

    BASE_URL = "https://finnhub.io/api/v1"

    # Rate limit presets (calls per minute)
    TIER_LIMITS = {
        "free": {"per_minute": 60},
        "paid": {"per_minute": 300},  # Varies by plan
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        tier: str = "free",
        max_retries: Optional[int] = None
    ):
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("Finnhub API key required. Set FINNHUB_API_KEY environment variable.")

        # Use centralized rate limit config (tier from env var or parameter)
        self._rate_config = get_service_rate_config('finnhub')
        self.tier = self._rate_config.get('tier', tier.lower())
        self.max_retries = max_retries if max_retries is not None else self._rate_config['max_retries']

        # Get rate limits from centralized config (fallback to local TIER_LIMITS)
        limits = self.TIER_LIMITS.get(self.tier, self.TIER_LIMITS["free"])
        self.calls_per_minute = self._rate_config.get('per_minute') or limits["per_minute"]

        # Minimum delay from centralized config
        self._min_delay = self._rate_config.get('min_delay', 1.0)

        # Request tracking for rate limiting
        self._request_times: List[datetime] = []
        self._last_request_time: Optional[datetime] = None
        self._lock = Lock()

    def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limits."""
        with self._lock:
            now = datetime.now()

            # Enforce minimum delay between requests
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
            if len(self._request_times) >= self.calls_per_minute:
                oldest = min(self._request_times)
                wait_time = (oldest + timedelta(minutes=1) - now).total_seconds()
                if wait_time > 0:
                    logger.debug("Rate limit: waiting %.1fs", wait_time)
                    time.sleep(wait_time + 0.1)
                    now = datetime.now()
                    one_minute_ago = now - timedelta(minutes=1)
                    self._request_times = [t for t in self._request_times if t > one_minute_ago]

            self._last_request_time = now
            self._request_times.append(now)

    def _make_request(self, endpoint: str, params: Dict[str, str]) -> Dict[str, Any]:
        """Make an API request with rate limiting and retry logic."""
        params["token"] = self.api_key
        url = f"{self.BASE_URL}/{endpoint}"

        last_error = None
        for attempt in range(self.max_retries):
            try:
                self._wait_for_rate_limit()

                response = requests.get(url, params=params, timeout=30)

                # Handle forbidden - symbol not available or API access issue
                if response.status_code == 403:
                    return None  # Symbol not available, don't retry

                # Handle rate limit response
                if response.status_code == 429:
                    if not should_retry(attempt, self._rate_config):
                        logger.warning("Rate limited (429). Max retries reached, failing fast.")
                        return None
                    wait_time = calculate_backoff(attempt, self._rate_config)
                    logger.warning(
                        "Rate limited (429). Waiting %.1fs (retry %d/%d)",
                        wait_time, attempt + 1, self.max_retries
                    )
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                data = response.json()

                # Check for API error in response
                if isinstance(data, dict) and data.get("error"):
                    error_msg = data.get("error", "Unknown error")
                    raise Exception(f"API error: {error_msg}")

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

        raise Exception(f"Max retries exceeded: {last_error}")

    def get_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current quote information for a symbol.
        Returns dict with regularMarketPrice, volume, etc.
        """
        params = {"symbol": symbol}

        data = self._make_request("quote", params)

        if not data or data.get("c") is None or data.get("c") == 0:
            return None

        # Map Finnhub fields to our format (matching yfinance structure)
        # Finnhub quote response: c=current, d=change, dp=percent change, h=high, l=low, o=open, pc=previous close
        try:
            return {
                "regularMarketPrice": float(data.get("c", 0)),
                "regularMarketChangePercent": float(data.get("dp", 0)),
                "volume": None,  # Quote endpoint doesn't include volume
                "regularMarketOpen": float(data.get("o", 0)),
                "regularMarketDayHigh": float(data.get("h", 0)),
                "regularMarketDayLow": float(data.get("l", 0)),
                "regularMarketPreviousClose": float(data.get("pc", 0)),
                "symbol": symbol
            }
        except (ValueError, TypeError) as e:
            logger.warning("Error parsing quote data: %s", e, extra={'symbol': symbol})
            return None

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
            period: Time period - '1d', '5d', '1mo'
            interval: Data interval - '5m', '15m', '1d'

        Returns:
            List of dicts with 'date' and 'close' keys
        """
        # Map interval to Finnhub resolution
        resolution_map = {
            "5m": "5",
            "5min": "5",
            "15m": "15",
            "15min": "15",
            "1d": "D",
            "daily": "D",
        }
        resolution = resolution_map.get(interval)
        if not resolution:
            raise ValueError(f"Unsupported interval: {interval}")

        # Calculate time range based on period
        now = datetime.now()
        if period == "1d":
            start_time = now - timedelta(days=1)
        elif period == "5d":
            start_time = now - timedelta(days=5)
        elif period == "1mo":
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(days=30)

        # Convert to UNIX timestamps
        from_ts = int(start_time.timestamp())
        to_ts = int(now.timestamp())

        params = {
            "symbol": symbol,
            "resolution": resolution,
            "from": str(from_ts),
            "to": str(to_ts),
        }

        data = self._make_request("stock/candle", params)

        if not data or data.get("s") == "no_data":
            return None

        # Extract data from response (full OHLCV)
        opens = data.get("o", [])
        highs = data.get("h", [])
        lows = data.get("l", [])
        closes = data.get("c", [])
        volumes = data.get("v", [])
        timestamps = data.get("t", [])

        if not closes or not timestamps:
            return None

        # Convert to our format
        result = []
        for i, ts in enumerate(timestamps):
            try:
                dt = datetime.fromtimestamp(ts)
                result.append({
                    "date": dt.isoformat(),
                    "open": float(opens[i]) if i < len(opens) else None,
                    "high": float(highs[i]) if i < len(highs) else None,
                    "low": float(lows[i]) if i < len(lows) else None,
                    "close": float(closes[i]) if i < len(closes) else None,
                    "volume": int(volumes[i]) if i < len(volumes) else None,
                    "adjusted_close": None,
                })
            except (ValueError, TypeError):
                continue

        return result if result else None

    def get_remaining_calls(self) -> Dict[str, Any]:
        """Get information about remaining rate limit quota."""
        with self._lock:
            now = datetime.now()
            one_minute_ago = now - timedelta(minutes=1)
            recent_requests = len([t for t in self._request_times if t > one_minute_ago])

            return {
                "calls_this_minute": recent_requests,
                "remaining_this_minute": self.calls_per_minute - recent_requests,
                "tier": self.tier
            }

    def get_market_holidays(self, exchange: str = "US") -> Optional[Dict[str, Any]]:
        """
        Get market holidays for an exchange.

        Args:
            exchange: Exchange code (default: "US" for US markets)

        Returns:
            Dict with 'data' (list of holidays), 'exchange', and 'timezone',
            or None if request fails.

            Each holiday in 'data' has:
            - eventName: Name of the holiday
            - atDate: Date string (YYYY-MM-DD)
            - tradingHour: Trading hours if partial close, empty if full close
        """
        params = {"exchange": exchange}

        try:
            data = self._make_request("stock/market-holiday", params)
            return data
        except Exception as e:
            logger.error("Error fetching market holidays: %s", e, extra={'exchange': exchange})
            return None
