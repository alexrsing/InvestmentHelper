import time
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from threading import Lock

from logging_config import get_logger
from rate_limit import get_service_rate_config, calculate_backoff, should_retry

logger = get_logger(__name__)


class FMPService:
    """
    Financial Modeling Prep API service with configurable rate limiting.

    Free tier: 250 API calls/day
    Starter tier: 300 API calls/minute
    Premium tier: 750 API calls/minute
    Ultimate tier: 3000 API calls/minute
    """

    BASE_URL = "https://financialmodelingprep.com/stable"

    # Rate limit presets
    TIER_LIMITS = {
        "free": {"per_day": 250, "per_minute": None},
        "starter": {"per_day": None, "per_minute": 300},
        "premium": {"per_day": None, "per_minute": 750},
        "ultimate": {"per_day": None, "per_minute": 3000},
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        tier: str = "free",
        max_retries: Optional[int] = None
    ):
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("FMP API key required. Set FMP_API_KEY environment variable.")

        # Use centralized rate limit config (tier from env var or parameter)
        self._rate_config = get_service_rate_config('fmp')
        self.tier = self._rate_config.get('tier', tier.lower())
        self.max_retries = max_retries if max_retries is not None else self._rate_config['max_retries']

        # Get rate limits for tier
        limits = self.TIER_LIMITS.get(self.tier, self.TIER_LIMITS["free"])
        self.calls_per_day = limits["per_day"]
        self.calls_per_minute = limits["per_minute"]

        # Minimum delay between requests
        if self.tier == "free":
            # Free tier: spread 250 calls over the day, but don't be too aggressive
            self._min_delay = 2.0
        else:
            self._min_delay = 0.5

        # Request tracking for rate limiting
        self._request_times: List[datetime] = []
        self._daily_count: int = 0
        self._daily_reset: datetime = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        self._last_request_time: Optional[datetime] = None
        self._lock = Lock()

    def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limits."""
        with self._lock:
            now = datetime.now()

            # Reset daily counter if new day
            if now >= self._daily_reset:
                self._daily_count = 0
                self._daily_reset = now.replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) + timedelta(days=1)

            # Check daily limit (free tier)
            if self.calls_per_day and self._daily_count >= self.calls_per_day:
                raise Exception(f"Daily rate limit ({self.calls_per_day}) exceeded. Resets at midnight.")

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

            # Wait if at per-minute limit (paid tiers)
            if self.calls_per_minute and len(self._request_times) >= self.calls_per_minute:
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
            self._daily_count += 1

    def _make_request(self, endpoint: str, params: Optional[Dict[str, str]] = None) -> Any:
        """Make an API request with rate limiting and retry logic."""
        if params is None:
            params = {}
        params["apikey"] = self.api_key
        url = f"{self.BASE_URL}/{endpoint}"

        last_error = None
        for attempt in range(self.max_retries):
            try:
                self._wait_for_rate_limit()

                response = requests.get(url, params=params, timeout=30)

                # Handle payment required - symbol not available on free tier
                if response.status_code == 402:
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

                # Handle forbidden - invalid API key or endpoint
                if response.status_code == 403:
                    raise Exception("API access forbidden (403). Check API key and endpoint.")

                response.raise_for_status()
                data = response.json()

                # Check for API error in response
                if isinstance(data, dict) and "Error Message" in data:
                    raise Exception(f"API error: {data['Error Message']}")

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
        data = self._make_request("quote", {"symbol": symbol})

        if not data or not isinstance(data, list) or len(data) == 0:
            return None

        quote = data[0]

        # Check if we got valid data
        if not quote or quote.get("price") is None or quote.get("price") == 0:
            return None

        # Map FMP fields to our format (matching yfinance structure)
        try:
            # FMP uses 'changePercentage' in stable API
            change_pct = quote.get("changePercentage") or quote.get("changesPercentage") or 0
            return {
                "regularMarketPrice": float(quote.get("price", 0)),
                "regularMarketChangePercent": float(change_pct),
                "volume": int(quote.get("volume", 0)) if quote.get("volume") else None,
                "regularMarketOpen": float(quote.get("open", 0)) if quote.get("open") else None,
                "regularMarketDayHigh": float(quote.get("dayHigh", 0)) if quote.get("dayHigh") else None,
                "regularMarketDayLow": float(quote.get("dayLow", 0)) if quote.get("dayLow") else None,
                "regularMarketPreviousClose": float(quote.get("previousClose", 0)) if quote.get("previousClose") else None,
                "symbol": quote.get("symbol", symbol)
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
        # Map interval to FMP endpoint
        if interval in ("5m", "5min"):
            endpoint = "historical-chart/5min"
        elif interval in ("15m", "15min"):
            endpoint = "historical-chart/15min"
        elif interval in ("1d", "daily"):
            endpoint = "historical-price-eod/full"
        else:
            raise ValueError(f"Unsupported interval: {interval}")

        data = self._make_request(endpoint, {"symbol": symbol})

        if not data:
            return None

        # Handle different response formats
        if interval in ("1d", "daily"):
            # Daily data has nested structure
            if isinstance(data, dict):
                historical = data.get("historical", [])
            else:
                historical = data
        else:
            # Intraday data is a list
            historical = data if isinstance(data, list) else []

        if not historical:
            return None

        # Convert to our format and filter by period
        result = []
        now = datetime.now()

        # Calculate cutoff based on period
        if period == "1d":
            cutoff = now - timedelta(days=1)
        elif period == "5d":
            cutoff = now - timedelta(days=5)
        elif period == "1mo":
            cutoff = now - timedelta(days=30)
        else:
            cutoff = now - timedelta(days=30)

        for item in historical:
            try:
                # Parse date - FMP uses 'date' field
                date_str = item.get("date", "")
                if not date_str:
                    continue

                # Parse datetime (format varies: "2024-01-15" or "2024-01-15 09:30:00")
                if " " in date_str:
                    item_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                else:
                    item_date = datetime.strptime(date_str, "%Y-%m-%d")

                # Filter by cutoff
                if item_date < cutoff:
                    continue

                result.append({
                    "date": date_str,
                    "open": float(item.get("open", 0)) if item.get("open") is not None else None,
                    "high": float(item.get("high", 0)) if item.get("high") is not None else None,
                    "low": float(item.get("low", 0)) if item.get("low") is not None else None,
                    "close": float(item.get("close", 0)),
                    "volume": int(item.get("volume", 0)) if item.get("volume") is not None else None,
                    "adjusted_close": float(item.get("adjClose")) if item.get("adjClose") is not None else None,
                })
            except (ValueError, TypeError):
                continue

        # FMP returns newest first, reverse to get chronological order
        result.reverse()

        return result if result else None

    def get_remaining_requests(self) -> Dict[str, Any]:
        """Get information about remaining rate limit quota."""
        with self._lock:
            now = datetime.now()

            # Reset if needed
            if now >= self._daily_reset:
                self._daily_count = 0

            one_minute_ago = now - timedelta(minutes=1)
            recent_requests = len([t for t in self._request_times if t > one_minute_ago])

            result = {
                "requests_today": self._daily_count,
                "tier": self.tier
            }

            if self.calls_per_day:
                result["remaining_today"] = self.calls_per_day - self._daily_count
            else:
                result["remaining_today"] = "unlimited"

            if self.calls_per_minute:
                result["requests_this_minute"] = recent_requests
                result["remaining_this_minute"] = self.calls_per_minute - recent_requests

            return result
