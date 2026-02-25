"""Service for updating risk ranges on the shared etfs DynamoDB table."""

from datetime import datetime, timezone
from typing import Any, Dict, List

from pynamodb.exceptions import DoesNotExist

from models import ETF
from util.logger import Logger

logger = Logger(__name__)


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
