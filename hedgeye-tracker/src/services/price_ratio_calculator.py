"""
Service for calculating price ratios between source and target symbols.

Fetches prices from DynamoDB (etf_monitoring_etf_prices table) which is
populated by a separate price-fetcher project.
"""

import os
from decimal import Decimal
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

from util.logging_config import get_logger

logger = get_logger(__name__)

# Price table name
PRICE_TABLE_NAME = os.getenv("PRICE_TABLE_NAME", "etfs")


class PriceRatioCalculator:
    """Calculate price ratios for symbol mapping adjustments"""

    def __init__(self):
        self.price_cache: Dict[str, float] = {}
        self._dynamodb = None

    @property
    def dynamodb(self):
        """Lazy initialization of DynamoDB resource"""
        if self._dynamodb is None:
            region = os.getenv("AWS_REGION") or os.getenv("AWS_REGION_NAME", "us-east-1")
            self._dynamodb = boto3.resource("dynamodb", region_name=region)
        return self._dynamodb

    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get the current price for a symbol from DynamoDB.

        Args:
            symbol: Ticker symbol

        Returns:
            Current price or None if unavailable
        """
        # Check cache first
        if symbol in self.price_cache:
            return self.price_cache[symbol]

        try:
            table = self.dynamodb.Table(PRICE_TABLE_NAME)
            response = table.get_item(Key={"ticker": symbol})

            if "Item" in response:
                item = response["Item"]
                price_str = item.get("current_price", "0")
                # Handle both string and Decimal types
                if isinstance(price_str, Decimal):
                    price = float(price_str)
                else:
                    price = float(price_str)
                self.price_cache[symbol] = price
                logger.info(f"Fetched price for {symbol} from DynamoDB: ${price:,.2f}")
                return price
            else:
                logger.warning(f"No price data in DynamoDB for {symbol}")
                return None

        except ClientError as e:
            logger.error(f"DynamoDB error fetching price for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    def calculate_ratio(
        self, source_symbol: str, target_symbol: str, source_price: Optional[float] = None
    ) -> Optional[float]:
        """
        Calculate the price ratio between source and target symbols

        Args:
            source_symbol: Source symbol (e.g., BITCOIN)
            target_symbol: Target symbol (e.g., IBIT)
            source_price: Optional source price from email data (prev_close or recent_price)

        Returns:
            Ratio (target_price / source_price) or None if calculation fails
        """
        try:
            # Get source price (use provided price or fetch current)
            if source_price is None:
                source_price = self.get_current_price(source_symbol)
                if source_price is None:
                    logger.warning(f"Could not get source price for {source_symbol}")
                    return None

            # Get target price
            target_price = self.get_current_price(target_symbol)
            if target_price is None:
                logger.warning(f"Could not get target price for {target_symbol}")
                return None

            # Calculate ratio
            if source_price == 0:
                logger.error(f"Source price is zero for {source_symbol}")
                return None

            ratio = target_price / source_price
            logger.info(
                f"Price ratio {target_symbol}/{source_symbol}: {ratio:.6f} "
                f"(${target_price:,.2f} / ${source_price:,.2f})"
            )
            return ratio

        except Exception as e:
            logger.error(f"Error calculating ratio for {source_symbol} -> {target_symbol}: {e}")
            return None

    def adjust_range(self, value: float, ratio: float) -> float:
        """
        Adjust a range value by applying the price ratio

        Args:
            value: Original value
            ratio: Price ratio to apply

        Returns:
            Adjusted value
        """
        return value * ratio

    def clear_cache(self):
        """Clear the price cache"""
        self.price_cache.clear()
