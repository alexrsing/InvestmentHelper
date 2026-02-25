import time
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from threading import Lock

from logging_config import get_logger
from rate_limit import get_service_rate_config, calculate_backoff, should_retry

logger = get_logger(__name__)


class TwelveDataService:
    """
    Twelve Data API service with configurable rate limiting.

    Free tier: 8 credits/minute, 800 credits/day
    Each API call = 1 credit per symbol
    """

    BASE_URL = "https://api.twelvedata.com"

    # Rate limit presets (credits per minute / per day)
    TIER_LIMITS = {
        "free": {"per_minute": 8, "per_day": 800},
        "grow": {"per_minute": 800, "per_day": None},
        "pro": {"per_minute": 4000, "per_day": None},
        "enterprise": {"per_minute": 12000, "per_day": None},
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        tier: str = "free",
        max_retries: Optional[int] = None
    ):
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("Twelve Data API key required. Set TWELVEDATA_API_KEY environment variable.")

        # Use centralized rate limit config (tier from env var or parameter)
        self._rate_config = get_service_rate_config('twelvedata')
        self.tier = self._rate_config.get('tier', tier.lower())
        self.max_retries = max_retries if max_retries is not None else self._rate_config['max_retries']

        # Get rate limits from centralized config
        self.credits_per_minute = self._rate_config.get('per_minute') or self.TIER_LIMITS.get(self.tier, self.TIER_LIMITS["free"])["per_minute"]
        self.credits_per_day = self._rate_config.get('per_day')

        # Minimum delay from centralized config
        self._min_delay = self._rate_config.get('min_delay', 8.0 if self.tier == "free" else 0.5)

        # Request tracking for rate limiting
        self._credits_used_this_minute: int = 0
        self._minute_reset: datetime = datetime.now() + timedelta(minutes=1)
        self._daily_credits: int = 0
        self._daily_reset: datetime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        self._last_request_time: Optional[datetime] = None
        self._lock = Lock()

    def _wait_for_rate_limit(self, credits_needed: int = 1):
        """Wait if necessary to respect rate limits."""
        with self._lock:
            now = datetime.now()

            # Reset minute counter if new minute
            if now >= self._minute_reset:
                self._credits_used_this_minute = 0
                self._minute_reset = now + timedelta(minutes=1)

            # Reset daily counter if new day
            if now >= self._daily_reset:
                self._daily_credits = 0
                self._daily_reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

            # Check daily limit
            if self.credits_per_day and self._daily_credits >= self.credits_per_day:
                raise Exception(f"Daily credit limit ({self.credits_per_day}) exceeded. Resets at midnight.")

            # Enforce minimum delay between requests
            if self._last_request_time:
                elapsed = (now - self._last_request_time).total_seconds()
                if elapsed < self._min_delay:
                    sleep_time = self._min_delay - elapsed
                    time.sleep(sleep_time)
                    now = datetime.now()

            # Wait if at per-minute limit
            if self._credits_used_this_minute + credits_needed > self.credits_per_minute:
                wait_time = (self._minute_reset - now).total_seconds()
                if wait_time > 0:
                    logger.debug("Rate limit: waiting %.1fs for credits reset", wait_time)
                    time.sleep(wait_time + 0.1)
                    self._credits_used_this_minute = 0
                    self._minute_reset = datetime.now() + timedelta(minutes=1)

            self._last_request_time = datetime.now()
            self._credits_used_this_minute += credits_needed
            self._daily_credits += credits_needed

    def _make_request(self, endpoint: str, params: Dict[str, str]) -> Dict[str, Any]:
        """Make an API request with rate limiting and retry logic."""
        params["apikey"] = self.api_key
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
                if data.get("status") == "error":
                    error_msg = data.get("message", "Unknown error")
                    if "API credits" in error_msg or "rate limit" in error_msg.lower():
                        if not should_retry(attempt, self._rate_config):
                            logger.warning("%s. Max retries reached, failing fast.", error_msg)
                            return None
                        wait_time = calculate_backoff(attempt, self._rate_config)
                        logger.warning(
                            "%s. Waiting %.1fs (retry %d/%d)",
                            error_msg, wait_time, attempt + 1, self.max_retries
                        )
                        time.sleep(wait_time)
                        continue
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
        params = {
            "symbol": symbol,
        }

        data = self._make_request("quote", params)

        if not data or data.get("status") == "error":
            return None

        # Map Twelve Data fields to our format (matching yfinance structure)
        try:
            close_price = float(data.get("close", 0))
            prev_close = float(data.get("previous_close", 0))
            change_percent = ((close_price - prev_close) / prev_close * 100) if prev_close else 0

            return {
                "regularMarketPrice": close_price,
                "regularMarketChangePercent": round(change_percent, 4),
                "volume": int(data.get("volume", 0)),
                "regularMarketOpen": float(data.get("open", 0)),
                "regularMarketDayHigh": float(data.get("high", 0)),
                "regularMarketDayLow": float(data.get("low", 0)),
                "regularMarketPreviousClose": prev_close,
                "symbol": data.get("symbol", symbol)
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
            period: Time period - '1d', '5d', '1mo' (used to calculate outputsize)
            interval: Data interval - '5min', '15min', '1day'

        Returns:
            List of dicts with 'date' and 'close' keys
        """
        # Map interval to Twelve Data format
        interval_map = {
            "5m": "5min",
            "5min": "5min",
            "15m": "15min",
            "15min": "15min",
            "1d": "1day",
            "daily": "1day",
        }
        td_interval = interval_map.get(interval)
        if not td_interval:
            raise ValueError(f"Unsupported interval: {interval}")

        # Calculate outputsize based on period and interval
        if period == "1d":
            if td_interval == "5min":
                outputsize = 78  # ~6.5 hours of trading
            elif td_interval == "15min":
                outputsize = 26
            else:
                outputsize = 1
        elif period == "5d":
            if td_interval == "5min":
                outputsize = 390  # 5 days * 78
            elif td_interval == "15min":
                outputsize = 130
            else:
                outputsize = 5
        elif period == "1mo":
            if td_interval == "1day":
                outputsize = 22  # ~22 trading days
            else:
                outputsize = 100  # Default for intraday
        else:
            outputsize = 30

        params = {
            "symbol": symbol,
            "interval": td_interval,
            "outputsize": str(outputsize),
        }

        data = self._make_request("time_series", params)

        if not data or data.get("status") == "error":
            return None

        values = data.get("values", [])
        if not values:
            return None

        # Convert to our format (full OHLCV)
        result = []
        for item in values:
            try:
                result.append({
                    "date": item.get("datetime", ""),
                    "open": float(item.get("open", 0)),
                    "high": float(item.get("high", 0)),
                    "low": float(item.get("low", 0)),
                    "close": float(item.get("close", 0)),
                    "volume": int(item.get("volume", 0)),
                    "adjusted_close": None,
                })
            except (ValueError, TypeError):
                continue

        # Reverse to get chronological order (Twelve Data returns newest first)
        result.reverse()

        return result if result else None

    def get_remaining_credits(self) -> Dict[str, Any]:
        """Get information about remaining rate limit quota."""
        with self._lock:
            now = datetime.now()

            # Reset if needed
            if now >= self._minute_reset:
                self._credits_used_this_minute = 0

            return {
                "credits_this_minute": self._credits_used_this_minute,
                "remaining_this_minute": self.credits_per_minute - self._credits_used_this_minute,
                "credits_today": self._daily_credits,
                "remaining_today": (self.credits_per_day - self._daily_credits) if self.credits_per_day else "unlimited",
                "tier": self.tier
            }
