"""
StockAnalysis.com price history file reader service.

Reads daily price history from JSON files downloaded from StockAnalysis.com.
Files are expected in the format: {SYMBOL}-price-history.json

File format:
{
  "status": 200,
  "data": [
    {
      "t": "2026-01-15",   # date
      "o": 239.31,         # open
      "h": 240.65,         # high
      "l": 236.63,         # low
      "c": 238.18,         # close
      "v": 43003571,       # volume
      "a": 238.18,         # adjusted close
      "ch": 0.65           # change percent
    },
    ...
  ]
}
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from logging_config import get_logger

logger = get_logger(__name__)


class StockAnalysisService:
    """
    Service for reading StockAnalysis.com price history JSON files.
    """

    # Pattern for extracting symbol from filename
    FILENAME_PATTERN = re.compile(r'^([A-Z0-9]+)-price-history\.json$')

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize the service.

        Args:
            data_dir: Directory containing StockAnalysis JSON files.
                      If not provided, must be specified in method calls.
        """
        self.data_dir = Path(data_dir) if data_dir else None

    def _get_data_dir(self, data_dir: Optional[str] = None) -> Path:
        """Get the data directory, preferring method argument over instance default."""
        if data_dir:
            return Path(data_dir)
        if self.data_dir:
            return self.data_dir
        raise ValueError("No data directory specified")

    def list_symbols(self, data_dir: Optional[str] = None) -> List[str]:
        """
        List all symbols available in the data directory.

        Args:
            data_dir: Directory to scan (optional, uses instance default)

        Returns:
            List of symbol strings (e.g., ['AAPL', 'AMZN', ...])
        """
        dir_path = self._get_data_dir(data_dir)
        if not dir_path.exists():
            return []

        symbols = []
        for filename in os.listdir(dir_path):
            match = self.FILENAME_PATTERN.match(filename)
            if match:
                symbols.append(match.group(1))

        return sorted(symbols)

    def get_file_path(self, symbol: str, data_dir: Optional[str] = None) -> Path:
        """
        Get the file path for a symbol's price history.

        Args:
            symbol: Stock/ETF symbol
            data_dir: Directory containing the files

        Returns:
            Path to the JSON file
        """
        dir_path = self._get_data_dir(data_dir)
        return dir_path / f"{symbol.upper()}-price-history.json"

    def read_raw_file(self, symbol: str, data_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Read raw JSON data from a StockAnalysis file.

        Args:
            symbol: Stock/ETF symbol
            data_dir: Directory containing the files

        Returns:
            Raw JSON dict or None if file not found/invalid
        """
        file_path = self.get_file_path(symbol, data_dir)

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Validate basic structure
            if not isinstance(data, dict):
                logger.warning("Invalid JSON structure", extra={'file': str(file_path)})
                return None

            if data.get("status") != 200:
                logger.warning(
                    "Non-200 status: %s", data.get('status'),
                    extra={'file': str(file_path)}
                )
                return None

            return data

        except json.JSONDecodeError as e:
            logger.error("Error parsing JSON: %s", e, extra={'file': str(file_path)})
            return None
        except IOError as e:
            logger.error("Error reading file: %s", e, extra={'file': str(file_path)})
            return None

    def get_historical_data(
        self,
        symbol: str,
        data_dir: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get historical price data for a symbol.

        Args:
            symbol: Stock/ETF symbol
            data_dir: Directory containing the files
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            List of dicts with 'date', 'open', 'high', 'low', 'close', 'volume', 'adjusted_close'
            Sorted by date ascending.
        """
        raw_data = self.read_raw_file(symbol, data_dir)
        if not raw_data:
            return None

        price_data = raw_data.get("data", [])
        if not price_data:
            return None

        result = []
        for item in price_data:
            try:
                date_str = item.get("t", "")

                # Apply date filters
                if start_date and date_str < start_date:
                    continue
                if end_date and date_str > end_date:
                    continue

                result.append({
                    "date": date_str,
                    "open": float(item.get("o", 0)),
                    "high": float(item.get("h", 0)),
                    "low": float(item.get("l", 0)),
                    "close": float(item.get("c", 0)),
                    "volume": int(item.get("v", 0)),
                    "adjusted_close": float(item.get("a", 0)),
                    "change_percent": float(item.get("ch", 0))
                })
            except (ValueError, TypeError):
                # Skip invalid records
                continue

        # Sort by date ascending
        result.sort(key=lambda x: x["date"])
        return result if result else None

    def get_info(self, symbol: str, data_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get current quote info for a symbol (most recent data point).

        Args:
            symbol: Stock/ETF symbol
            data_dir: Directory containing the files

        Returns:
            Dict with regularMarketPrice, volume, etc. matching yfinance format
        """
        history = self.get_historical_data(symbol, data_dir)
        if not history:
            return None

        # Get most recent data point
        latest = history[-1]

        return {
            "regularMarketPrice": latest["close"],
            "regularMarketChangePercent": latest["change_percent"],
            "volume": latest["volume"],
            "regularMarketOpen": latest["open"],
            "regularMarketDayHigh": latest["high"],
            "regularMarketDayLow": latest["low"],
            "symbol": symbol.upper()
        }

    def get_price_history_1d(
        self,
        symbol: str,
        data_dir: Optional[str] = None,
        days: int = 30
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get daily price history in the format expected by the database.

        Args:
            symbol: Stock/ETF symbol
            data_dir: Directory containing the files
            days: Number of days of history to return (0 = all)

        Returns:
            List of dicts with 'date' and 'close' keys, most recent last
        """
        history = self.get_historical_data(symbol, data_dir)
        if not history:
            return None

        # Limit to requested number of days
        if days > 0:
            history = history[-days:]

        # Convert to simplified format
        return [
            {"date": item["date"], "close": item["close"]}
            for item in history
        ]

    def get_full_price_history(
        self,
        symbol: str,
        data_dir: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get full daily price history with all OHLCV data.

        Args:
            symbol: Stock/ETF symbol
            data_dir: Directory containing the files

        Returns:
            List of dicts with date, open, high, low, close, volume, adjusted_close
        """
        return self.get_historical_data(symbol, data_dir)

    def get_date_range(
        self,
        symbol: str,
        data_dir: Optional[str] = None
    ) -> Optional[tuple[str, str]]:
        """
        Get the date range of available data for a symbol.

        Args:
            symbol: Stock/ETF symbol
            data_dir: Directory containing the files

        Returns:
            Tuple of (start_date, end_date) as strings, or None
        """
        history = self.get_historical_data(symbol, data_dir)
        if not history:
            return None

        return (history[0]["date"], history[-1]["date"])

    def get_summary(self, data_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a summary of available data in the directory.

        Args:
            data_dir: Directory to scan

        Returns:
            Dict with symbol count, date range, etc.
        """
        symbols = self.list_symbols(data_dir)

        if not symbols:
            return {
                "symbol_count": 0,
                "symbols": [],
                "date_range": None
            }

        # Sample a few symbols to get date range
        min_date = None
        max_date = None

        for symbol in symbols[:10]:  # Sample first 10
            date_range = self.get_date_range(symbol, data_dir)
            if date_range:
                if min_date is None or date_range[0] < min_date:
                    min_date = date_range[0]
                if max_date is None or date_range[1] > max_date:
                    max_date = date_range[1]

        return {
            "symbol_count": len(symbols),
            "symbols": symbols,
            "date_range": (min_date, max_date) if min_date else None
        }
