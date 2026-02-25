"""
Transformer service for converting parsed trend range email data into trend range database format
"""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from services.price_ratio_calculator import PriceRatioCalculator
from util.logger import Logger

logger = Logger(__name__)


class TrendRangeTransformer:
    """Transform parsed trend range data for database storage"""

    def __init__(self):
        self.price_calculator = PriceRatioCalculator()

    def transform_for_database(self, trend_range_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform trend range email data into trend range database format.

        Args:
            trend_range_data: List of parsed trend range records from emails

        Returns:
            List of trend range records ready for database storage
        """
        # Group records by ticker to find the most recent data and build history
        grouped_data = defaultdict(list)

        for record in trend_range_data:
            ticker = record.get("etf_symbol")
            if ticker:
                grouped_data[ticker].append(record)

        # Transform each ticker's data
        transformed_records = []

        for ticker, records in grouped_data.items():
            # Sort by email date (most recent first)
            sorted_records = sorted(
                records, key=lambda x: self._parse_email_date(x.get("email_date", "")), reverse=True
            )

            # Most recent record becomes current data
            most_recent = sorted_records[0]

            # Check if symbol mapping occurred and apply price ratio adjustment
            adjusted_data = self._apply_price_ratio_adjustment(most_recent)

            # Build current data with adjusted values
            current_data = {
                "trend_low": adjusted_data["trend_low"],
                "trend_high": adjusted_data["trend_high"],
                "recent_price": adjusted_data.get("recent_price"),
                "trend": most_recent.get("trend", "NEUTRAL"),
                "asset_class": most_recent.get("asset_class"),
                "last_updated": datetime.now().isoformat(),
                "source": most_recent.get("source", "gmail_hedgeye_etf_pro_plus"),
            }

            # Build history entry from the most recent record with adjusted values
            history_entry = {
                "timestamp": self._parse_email_date(most_recent.get("email_date", "")).isoformat(),
                "range": [Decimal(adjusted_data["trend_low"]), Decimal(adjusted_data["trend_high"])],
            }

            transformed_records.append(
                {
                    "etf_symbol": ticker,
                    "current_data": current_data,
                    "history_entry": history_entry,
                    "all_history": self._build_all_history_with_adjustment(sorted_records),
                }
            )

        return transformed_records

    def _apply_price_ratio_adjustment(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply price ratio adjustment if symbol mapping occurred.

        Args:
            record: Trend range record

        Returns:
            Dictionary with adjusted trend_low, trend_high, recent_price
        """
        original_symbol = record.get("original_symbol")
        etf_symbol = record.get("etf_symbol")
        range_low = float(record.get("range_low", 0))
        range_high = float(record.get("range_high", 0))
        recent_price_str = record.get("recent_price")
        recent_price = float(recent_price_str) if recent_price_str else None

        # Check if mapping occurred
        if original_symbol and etf_symbol and original_symbol != etf_symbol:
            logger.info(f"Symbol mapping detected: {original_symbol} -> {etf_symbol}")

            # Calculate price ratio using recent_price as source price
            if recent_price and recent_price > 0:
                ratio = self.price_calculator.calculate_ratio(original_symbol, etf_symbol, source_price=recent_price)

                if ratio:
                    # Apply ratio to adjust ranges
                    adjusted_low = self.price_calculator.adjust_range(range_low, ratio)
                    adjusted_high = self.price_calculator.adjust_range(range_high, ratio)
                    adjusted_recent = self.price_calculator.adjust_range(recent_price, ratio)

                    logger.info(
                        f"Adjusted ranges for {etf_symbol}: "
                        f"Low: {range_low:,.2f} -> {adjusted_low:,.2f}, "
                        f"High: {range_high:,.2f} -> {adjusted_high:,.2f}"
                    )

                    return {
                        "trend_low": str(adjusted_low),
                        "trend_high": str(adjusted_high),
                        "recent_price": str(adjusted_recent),
                    }
                else:
                    logger.warning(
                        f"Could not calculate ratio for {original_symbol} -> {etf_symbol}, using original values"
                    )
            else:
                logger.warning("No recent_price available for ratio calculation, using original values")

        # No mapping or adjustment failed, return original values
        return {
            "trend_low": str(range_low),
            "trend_high": str(range_high),
            "recent_price": str(recent_price) if recent_price else None,
        }

    def _build_all_history_with_adjustment(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Build complete history from all records with price ratio adjustments.

        Args:
            records: List of records sorted by date (most recent first)

        Returns:
            List of history entries with timestamp and range
        """
        history = []

        for record in records:
            adjusted_data = self._apply_price_ratio_adjustment(record)

            history_entry = {
                "timestamp": self._parse_email_date(record.get("email_date", "")).isoformat(),
                "range": [Decimal(adjusted_data["trend_low"]), Decimal(adjusted_data["trend_high"])],
            }
            history.append(history_entry)

        return history

    def _parse_email_date(self, email_date: str) -> datetime:
        """
        Parse email date string into datetime object.

        Args:
            email_date: Email date string (e.g., "Mon, 14 Oct 2025 15:30:00 -0400 (EDT)")

        Returns:
            datetime object
        """
        if not email_date:
            return datetime.now()

        try:
            # Try parsing RFC 2822 format (email date format)
            from email.utils import parsedate_to_datetime

            return parsedate_to_datetime(email_date)
        except Exception:
            # Fallback to current time if parsing fails
            return datetime.now()

    def _build_all_history(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Build complete history from all records (for initial data load).

        Args:
            records: List of records sorted by date (most recent first)

        Returns:
            List of history entries
        """
        history = []

        for record in records:
            history_entry = {
                "date": self._parse_email_date(record.get("email_date", "")).strftime("%Y-%m-%d"),
                "trend_low": record.get("range_low", "0"),
                "trend_high": record.get("range_high", "0"),
                "recent_price": record.get("recent_price"),
                "trend": record.get("trend", "NEUTRAL"),
                "asset_class": record.get("asset_class"),
                "email_date": record.get("email_date", ""),
                "email_id": record.get("email_id", ""),
            }
            history.append(history_entry)

        return history
