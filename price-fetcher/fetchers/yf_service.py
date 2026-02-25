import time
from typing import Dict, Any, List, Optional
from requests.exceptions import HTTPError

from logging_config import get_logger

logger = get_logger(__name__)

# yfinance is optional - not included in Lambda deployment
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    yf = None
    YFINANCE_AVAILABLE = False
    logger.info("yfinance not available - Yahoo Finance service disabled")


class YahooFinanceService:
    def __init__(self, request_delay: float = 1.0, max_retries: int = 5):
        if not YFINANCE_AVAILABLE:
            raise ImportError("yfinance is not installed. Install with: pip install yfinance")
        self.client = yf
        self.request_delay = request_delay
        self.max_retries = max_retries

    def _with_retry(self, operation_name: str, func):
        """Execute a function with retry logic for rate limiting and transient errors."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                time.sleep(self.request_delay)
                result = func()
                return result
            except HTTPError as e:
                last_error = e
                if e.response is not None and e.response.status_code == 429:
                    wait_time = (2 ** attempt) * 10  # 10s, 20s, 40s, 80s, 160s
                    logger.warning(
                        "Rate limited on %s. Waiting %ds (retry %d/%d)",
                        operation_name, wait_time, attempt + 1, self.max_retries
                    )
                    time.sleep(wait_time)
                else:
                    logger.warning("HTTP error on %s: %s", operation_name, e)
                    raise
            except Exception as e:
                last_error = e
                wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s for other errors
                logger.warning(
                    "Error on %s: %s. Waiting %ds (retry %d/%d)",
                    operation_name, e, wait_time, attempt + 1, self.max_retries
                )
                time.sleep(wait_time)

        raise Exception(f"Max retries exceeded for {operation_name}: {last_error}")

    def get_info(self, symbol: str) -> Optional[Dict[Any, Any]]:
        def fetch():
            # Create fresh Ticker each attempt to avoid cached bad state
            ticker = self.client.Ticker(symbol)
            return ticker.info

        return self._with_retry(f"get_info({symbol})", fetch)

    def get_historical_data(self, symbol: str, period: str, interval: str) -> Optional[List[Dict[str, Any]]]:
        def fetch():
            # Create fresh Ticker each attempt
            ticker = self.client.Ticker(symbol)
            return ticker.history(period=period, interval=interval)

        history = self._with_retry(f"get_history({symbol}, {period}, {interval})", fetch)

        if history is None or history.empty:
            return None

        result = []
        for date, row in history.iterrows():
            result.append({
                'date': date.isoformat(),
                'open': float(row['Open']) if 'Open' in row and row['Open'] == row['Open'] else None,
                'high': float(row['High']) if 'High' in row and row['High'] == row['High'] else None,
                'low': float(row['Low']) if 'Low' in row and row['Low'] == row['Low'] else None,
                'close': float(row['Close']) if 'Close' in row and row['Close'] == row['Close'] else None,
                'volume': int(row['Volume']) if 'Volume' in row and row['Volume'] == row['Volume'] else None,
                'adjusted_close': None,
            })
        return result if result else None