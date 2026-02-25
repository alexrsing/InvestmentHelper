"""
Transformer service for converting parsed risk range email data into trade range database format
"""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from services.price_ratio_calculator import PriceRatioCalculator
from util.logger import Logger

logger = Logger(__name__)


class TradeRangeTransformer:
    """Transform parsed risk range data for database storage"""

    def __init__(self):
        self.price_calculator = PriceRatioCalculator()

    def transform_for_database(self, risk_range_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform risk range email data into trade range database format.
        Applies price ratio adjustments when symbols are mapped.

        Args:
            risk_range_data: List of parsed risk range records from emails

        Returns:
            List of trade range records ready for database storage
        """
        # Group records by ticker to find the most recent data and build history
        grouped_data = defaultdict(list)

        for record in risk_range_data:
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
                "trade_low": adjusted_data["trade_low"],
                "trade_high": adjusted_data["trade_high"],
                "prev_close": adjusted_data.get("prev_close"),
                "trend": most_recent.get("trend", "NEUTRAL"),
                "last_updated": datetime.now().isoformat(),
                "source": most_recent.get("source", "gmail_hedgeye_risk_range"),
            }

            # Build history entry from the most recent record with adjusted values
            history_entry = {
                "timestamp": self._parse_email_date(most_recent.get("email_date", "")).isoformat(),
                "range": [Decimal(adjusted_data["trade_low"]), Decimal(adjusted_data["trade_high"])],
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
            record: Risk range record

        Returns:
            Dictionary with adjusted trade_low, trade_high, prev_close
        """
        original_symbol = record.get("original_symbol")
        etf_symbol = record.get("etf_symbol")
        buy_trade = float(record.get("buy_trade", 0))
        sell_trade = float(record.get("sell_trade", 0))
        prev_close_str = record.get("prev_close")
        prev_close = float(prev_close_str) if prev_close_str else None

        # Check if mapping occurred
        if original_symbol and etf_symbol and original_symbol != etf_symbol:
            logger.info(f"Symbol mapping detected: {original_symbol} -> {etf_symbol}")

            # Calculate price ratio using prev_close as source price
            if prev_close and prev_close > 0:
                ratio = self.price_calculator.calculate_ratio(original_symbol, etf_symbol, source_price=prev_close)

                if ratio:
                    # Apply ratio to adjust ranges
                    adjusted_buy = self.price_calculator.adjust_range(buy_trade, ratio)
                    adjusted_sell = self.price_calculator.adjust_range(sell_trade, ratio)
                    adjusted_prev_close = self.price_calculator.adjust_range(prev_close, ratio)

                    logger.info(
                        f"Adjusted ranges for {etf_symbol}: "
                        f"Low: {buy_trade:,.2f} -> {adjusted_buy:,.2f}, "
                        f"High: {sell_trade:,.2f} -> {adjusted_sell:,.2f}"
                    )

                    return {
                        "trade_low": str(adjusted_buy),
                        "trade_high": str(adjusted_sell),
                        "prev_close": str(adjusted_prev_close),
                    }
                else:
                    logger.warning(
                        f"Could not calculate ratio for {original_symbol} -> {etf_symbol}, using original values"
                    )
            else:
                logger.warning("No prev_close available for ratio calculation, using original values")

        # No mapping or adjustment failed, return original values
        return {
            "trade_low": str(buy_trade),
            "trade_high": str(sell_trade),
            "prev_close": str(prev_close) if prev_close else None,
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
                "range": [Decimal(adjusted_data["trade_low"]), Decimal(adjusted_data["trade_high"])],
            }
            history.append(history_entry)

        return history

    def _parse_email_date(self, email_date: str) -> datetime:
        """
        Parse email date string into datetime object.

        Args:
            email_date: Email date string (e.g., "Wed, 15 Oct 2025 07:43:03 -0400 (EDT)")

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
                "trade_low": record.get("buy_trade", "0"),
                "trade_high": record.get("sell_trade", "0"),
                "prev_close": record.get("prev_close"),
                "trend": record.get("trend", "NEUTRAL"),
                "email_date": record.get("email_date", ""),
                "email_id": record.get("email_id", ""),
            }
            history.append(history_entry)

        return history
