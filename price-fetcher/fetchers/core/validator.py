"""
Core price data validation logic.

Validates price data completeness for symbols against expected trading days.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from logging_config import get_logger

logger = get_logger(__name__)


class PriceValidator:
    """
    Validates price data completeness.

    Can validate:
    - Daily price history (checks for missing trading days)
    - Intraday 5-minute data (checks for missing intervals)
    """

    def __init__(self):
        """Initialize the validator."""
        pass

    def get_trading_days(self, start_date: date, end_date: date) -> Set[date]:
        """
        Get all trading days between start and end dates.

        Excludes weekends and market holidays.

        Args:
            start_date: Start date for range
            end_date: End date for range

        Returns:
            Set of trading day dates
        """
        try:
            from pricedata import is_trading_day
        except ImportError:
            logger.warning("pricedata package not available, using weekday-only check")
            # Fallback: just exclude weekends
            trading_days = set()
            current = start_date
            while current <= end_date:
                if current.weekday() < 5:
                    trading_days.add(current)
                current += timedelta(days=1)
            return trading_days

        trading_days = set()
        current = start_date

        while current <= end_date:
            if is_trading_day(current):
                trading_days.add(current)
            current += timedelta(days=1)

        return trading_days

    def get_price_dates(self, symbol: str, start_date: date, end_date: date) -> Set[date]:
        """
        Get dates with price data for a symbol.

        Args:
            symbol: Stock/ETF symbol
            start_date: Start date
            end_date: End date

        Returns:
            Set of dates that have price data
        """
        try:
            from pricedata import get_price_history
        except ImportError:
            logger.error("pricedata package not available")
            return set()

        history = get_price_history(symbol, start_date, end_date)
        return set(history.keys())

    def validate_daily(
        self,
        symbol: str,
        first_trade_date: date,
        end_date: date
    ) -> Tuple[bool, List[date]]:
        """
        Validate daily price history completeness for a symbol.

        Args:
            symbol: Stock/ETF symbol
            first_trade_date: First trade date for this symbol
            end_date: End date for validation

        Returns:
            Tuple of (is_complete, list_of_missing_dates)
        """
        # Get expected trading days
        expected_days = self.get_trading_days(first_trade_date, end_date)

        # Get actual price dates
        actual_dates = self.get_price_dates(symbol, first_trade_date, end_date)

        # Find missing dates
        missing_dates = sorted(expected_days - actual_dates)

        if missing_dates:
            logger.debug(
                "Symbol %s missing %d days from %s to %s",
                symbol, len(missing_dates), first_trade_date, end_date
            )

        return len(missing_dates) == 0, missing_dates

    def get_expected_intraday_intervals(self, target_date: date) -> Set[str]:
        """
        Get expected 5-minute interval timestamps for a trading day.

        Regular hours: 9:30 AM - 4:00 PM ET (78 intervals)
        Early close: 9:30 AM - 1:00 PM ET (43 intervals)

        Args:
            target_date: Trading day to generate intervals for

        Returns:
            Set of ISO timestamp strings (e.g., "2025-01-22T09:30:00")
        """
        try:
            from pricedata import is_early_close
            early_close_hours = is_early_close(target_date)
        except ImportError:
            early_close_hours = None

        if early_close_hours:
            # Parse early close time from format "09:30-13:00"
            parts = early_close_hours.split('-')
            if len(parts) == 2:
                market_close_str = parts[1].strip()
            else:
                market_close_str = "16:00"
        else:
            market_close_str = "16:00"

        # Parse close time
        close_hour, close_minute = map(int, market_close_str.split(':'))

        intervals = set()
        current_hour = 9
        current_minute = 30

        # Generate 5-minute intervals from 9:30 to market close
        while True:
            timestamp = f"{target_date}T{current_hour:02d}:{current_minute:02d}:00"
            intervals.add(timestamp)

            if current_hour == close_hour and current_minute == close_minute:
                break

            current_minute += 5
            if current_minute >= 60:
                current_minute = 0
                current_hour += 1

            if current_hour > 16:
                break

        return intervals

    def validate_intraday(
        self,
        symbol: str,
        end_date: date,
        lookback_days: int = 10
    ) -> Tuple[bool, List[str]]:
        """
        Validate 5-minute intraday price history completeness for a symbol.

        Args:
            symbol: Stock/ETF symbol
            end_date: End date for validation
            lookback_days: Number of calendar days to check (default: 10)

        Returns:
            Tuple of (is_complete, list_of_missing_intervals)
        """
        try:
            from pricedata.client import _get_db
        except ImportError:
            logger.error("pricedata package not available")
            return False, []

        db = _get_db()
        data = db.get_price_data(symbol.upper())

        start_date = end_date - timedelta(days=lookback_days)
        expected_trading_days = self.get_trading_days(start_date, end_date)

        if not data:
            logger.debug("No data found for %s", symbol)
            all_intervals = set()
            for day in expected_trading_days:
                all_intervals.update(self.get_expected_intraday_intervals(day))
            return False, sorted(all_intervals)

        # Check for 5-minute data
        history_5m = data.get('price_history_5m', [])

        if not history_5m:
            logger.debug("No 5-minute data for %s", symbol)
            all_intervals = set()
            for day in expected_trading_days:
                all_intervals.update(self.get_expected_intraday_intervals(day))
            return False, sorted(all_intervals)

        # Extract actual intervals
        actual_intervals = set()
        for item in history_5m:
            timestamp = item.get('date', '')
            if timestamp:
                # Normalize to remove microseconds
                if len(timestamp) > 19:
                    timestamp = timestamp[:19]
                actual_intervals.add(timestamp)

        # Build expected intervals
        expected_intervals = set()
        for day in expected_trading_days:
            expected_intervals.update(self.get_expected_intraday_intervals(day))

        # Find missing intervals
        missing_intervals = sorted(expected_intervals - actual_intervals)

        if missing_intervals:
            logger.debug(
                "Symbol %s missing %d 5m intervals",
                symbol, len(missing_intervals)
            )

        return len(missing_intervals) == 0, missing_intervals

    def validate_symbols(
        self,
        symbols: List[str],
        interval: str = "daily",
        first_trade_dates: Optional[Dict[str, date]] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Validate price data for multiple symbols.

        This is the main entry point for batch validation.

        Args:
            symbols: List of symbols to validate
            interval: "daily" or "intraday"
            first_trade_dates: Dict mapping symbol to first trade date (for daily)
            end_date: End date for validation (default: today)

        Returns:
            Dict with validation results:
            - complete: List of complete symbols
            - incomplete: List of dicts with symbol, missing_count, missing_items
            - total: Total symbols checked
            - complete_count: Number of complete symbols
            - incomplete_count: Number of incomplete symbols
        """
        if end_date is None:
            end_date = date.today()

        if first_trade_dates is None:
            first_trade_dates = {}

        results = {
            "complete": [],
            "incomplete": [],
            "total": len(symbols),
            "complete_count": 0,
            "incomplete_count": 0,
            "interval": interval,
        }

        for symbol in symbols:
            if interval == "daily":
                # Use first trade date if available, otherwise 1 year ago
                first_date = first_trade_dates.get(
                    symbol,
                    end_date - timedelta(days=365)
                )
                is_complete, missing = self.validate_daily(symbol, first_date, end_date)
            else:
                is_complete, missing = self.validate_intraday(symbol, end_date)

            if is_complete:
                results["complete"].append(symbol)
                results["complete_count"] += 1
            else:
                results["incomplete"].append({
                    "symbol": symbol,
                    "missing_count": len(missing),
                    "first_missing": str(missing[0]) if missing else None,
                    "last_missing": str(missing[-1]) if missing else None,
                })
                results["incomplete_count"] += 1

        logger.info(
            "Validation complete: %d/%d symbols complete (%s interval)",
            results["complete_count"], results["total"], interval
        )

        return results
