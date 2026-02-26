"""Service for updating risk ranges on the shared etfs DynamoDB table."""

from datetime import datetime, timezone
from typing import Any, Dict, List

from pynamodb.exceptions import DoesNotExist

from models import ETF, ETFHistory
from util.logging_config import get_logger

logger = get_logger(__name__)


class ETFUpdateService:
    """Updates risk_range_low and risk_range_high on existing ETF records.

    Uses PynamoDB partial updates to avoid overwriting price fields
    managed by the price-fetcher service.
    """

    def update_risk_ranges(self, trade_ranges: List[Dict[str, Any]]) -> int:
        """
        Update risk ranges on existing ETF records in the shared etfs table.

        For each trade range record, sets risk_range_low (from buy_trade)
        and risk_range_high (from sell_trade) using partial updates.
        Only updates existing records - never creates new ones.

        Args:
            trade_ranges: List of trade range dicts with keys:
                - etf_symbol: ticker symbol
                - current_data: dict with trade_low and trade_high

        Returns:
            Number of ETF records successfully updated
        """
        updated_count = 0

        for trade_range in trade_ranges:
            ticker = trade_range.get("etf_symbol")
            current_data = trade_range.get("current_data", {})

            if not ticker:
                logger.warning("Skipping trade range with missing etf_symbol")
                continue

            try:
                low = float(current_data.get("trade_low", 0))
                high = float(current_data.get("trade_high", 0))
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid numeric values for {ticker}: {e}")
                continue

            if low <= 0 or high <= 0:
                logger.warning(f"Skipping {ticker}: invalid range values low={low}, high={high}")
                continue

            try:
                # Verify record exists first
                ETF.get(ticker)

                # Perform partial update - only touches risk range fields
                ETF(ticker=ticker).update(actions=[
                    ETF.risk_range_low.set(low),
                    ETF.risk_range_high.set(high),
                    ETF.updated_at.set(datetime.now(timezone.utc)),
                ])

                updated_count += 1
                logger.info(f"Updated risk ranges for {ticker}: low={low}, high={high}")

            except DoesNotExist:
                logger.warning(
                    f"Ticker {ticker} not found in etfs table - "
                    "price-fetcher must create the record first. Skipping."
                )
            except Exception as e:
                logger.error(f"Error updating risk ranges for {ticker}: {e}")

        logger.info(f"Updated risk ranges for {updated_count} ETFs")
        return updated_count

    def update_history_risk_ranges(self, trade_ranges: List[Dict[str, Any]]) -> int:
        """
        Update risk_range_low/risk_range_high on existing etf_history records.

        For each trade range, iterates all_history entries and performs partial
        updates on matching etf_history records. Skips records that don't exist.

        Args:
            trade_ranges: List of trade range dicts with keys:
                - etf_symbol: ticker symbol
                - all_history: list of dicts with 'timestamp' (ISO datetime)
                  and 'range' ([low, high] Decimals)

        Returns:
            Number of etf_history records successfully updated
        """
        updated_count = 0

        for trade_range in trade_ranges:
            ticker = trade_range.get("etf_symbol")
            all_history = trade_range.get("all_history", [])

            if not ticker:
                logger.warning("Skipping trade range with missing etf_symbol")
                continue

            for entry in all_history:
                timestamp = entry.get("timestamp", "")
                range_values = entry.get("range", [])

                if len(range_values) != 2:
                    logger.warning(f"Skipping history entry for {ticker}: invalid range {range_values}")
                    continue

                # Extract date as YYYY-MM-DD from ISO timestamp
                try:
                    date_str = datetime.fromisoformat(timestamp).strftime("%Y-%m-%d")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping history entry for {ticker}: invalid timestamp '{timestamp}': {e}")
                    continue

                low = float(range_values[0])
                high = float(range_values[1])

                if low <= 0 or high <= 0:
                    logger.warning(f"Skipping history entry for {ticker} on {date_str}: invalid range low={low}, high={high}")
                    continue

                try:
                    ETFHistory(ticker=ticker, date=date_str).update(
                        actions=[
                            ETFHistory.risk_range_low.set(low),
                            ETFHistory.risk_range_high.set(high),
                        ],
                        condition=(ETFHistory.ticker.exists()),
                    )
                    updated_count += 1
                    logger.debug(f"Updated history risk ranges for {ticker} on {date_str}: low={low}, high={high}")
                except Exception as e:
                    # Condition check failure means record doesn't exist — skip
                    logger.debug(f"No etf_history record for {ticker} on {date_str}, skipping: {e}")

        logger.info(f"Updated risk ranges on {updated_count} etf_history records")
        return updated_count
