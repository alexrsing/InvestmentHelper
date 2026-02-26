import os
from typing import Any, Dict, List, Optional

from services.database_service import DatabaseService
from services.etf_update_service import ETFUpdateService


class Database:
    def __init__(self):
        self.db_service = DatabaseService()
        self.etf_update_service = ETFUpdateService()
        self.trade_ranges_table = os.getenv(
            "TRADE_RANGES_TABLE", "hedgeye_daily_ranges"
        )
        self.trend_ranges_table = os.getenv(
            "TREND_RANGES_TABLE", "hedgeye_weekly_ranges"
        )

    def put_security_data(self, table_name: str, item: Dict[str, Any]) -> bool:
        return self.db_service.put_item(table_name, item)

    def batch_put_security_data(self, table_name: str, items: List[Dict[str, Any]]) -> bool:
        return self.db_service.batch_put_items(table_name, items)

    def get_security_data(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self.db_service.get_item(table_name, key)

    def save_trade_range(self, etf_symbol: str, current_data: Dict[str, Any], history: List[Dict[str, Any]]) -> bool:
        """
        Save a trade range record with full history.

        Args:
            etf_symbol: ETF symbol
            current_data: Current trade range data (trade_low, trade_high, etc.)
            history: Full list of historical entries

        Returns:
            True if successful
        """
        return self.db_service.save_item_with_history(
            table_name=self.trade_ranges_table,
            etf_symbol=etf_symbol,
            current_data=current_data,
            history=history,
            history_field="trade_history",
        )

    def save_trend_range(self, etf_symbol: str, current_data: Dict[str, Any], history: List[Dict[str, Any]]) -> bool:
        """
        Save a trend range record with full history.

        Args:
            etf_symbol: ETF symbol
            current_data: Current trend range data (trend_low, trend_high, etc.)
            history: Full list of historical entries

        Returns:
            True if successful
        """
        return self.db_service.save_item_with_history(
            table_name=self.trend_ranges_table,
            etf_symbol=etf_symbol,
            current_data=current_data,
            history=history,
            history_field="trend_history",
        )

    def batch_save_trade_ranges(self, trade_ranges: List[Dict[str, Any]]) -> int:
        """
        Save multiple trade range records with history tracking.

        Args:
            trade_ranges: List of trade range dictionaries

        Returns:
            Number of records saved
        """
        count = 0
        for trade_range in trade_ranges:
            etf_symbol = trade_range["etf_symbol"]
            current_data = trade_range["current_data"]
            all_history = trade_range["all_history"]

            if self.save_trade_range(etf_symbol, current_data, all_history):
                count += 1

        # Update the shared etfs table with latest risk ranges
        self.etf_update_service.update_risk_ranges(trade_ranges)

        # Update etf_history records with per-date risk ranges
        self.etf_update_service.update_history_risk_ranges(trade_ranges)

        return count

    def batch_save_trend_ranges(self, trend_ranges: List[Dict[str, Any]]) -> int:
        """
        Save multiple trend range records with history tracking.

        Args:
            trend_ranges: List of trend range dictionaries

        Returns:
            Number of records saved
        """
        count = 0
        for trend_range in trend_ranges:
            etf_symbol = trend_range["etf_symbol"]
            current_data = trend_range["current_data"]
            all_history = trend_range["all_history"]

            if self.save_trend_range(etf_symbol, current_data, all_history):
                count += 1

        return count
