import math
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from pynamodb.exceptions import DoesNotExist
from typing import Optional, Dict, List, Any

from logging_config import get_logger
from models import ETF, ETFHistory

logger = get_logger(__name__)


def _get_table_name(table_type: str) -> str:
    """
    Get table name for DynamoDB.

    Uses flat table names matching the InvestmentHelper convention.
    Supports env var overrides for flexibility.

    Args:
        table_type: One of 'prices', 'watchlist'

    Returns:
        Table name (e.g., 'etfs', 'watchlist')
    """
    # Environment variable overrides
    overrides = {
        'prices': 'PRICES_TABLE',
        'watchlist': 'WATCHLIST_TABLE',
    }

    env_var = overrides.get(table_type)
    if env_var:
        override = os.getenv(env_var)
        if override:
            return override

    # Default flat table names matching InvestmentHelper
    defaults = {
        'prices': 'etfs',
        'watchlist': 'watchlist',
    }
    return defaults.get(table_type, table_type)


class DBService:
    def __init__(self):
        region = os.getenv('AWS_REGION', 'us-east-1')
        self.dynamodb = boto3.resource('dynamodb', region_name=region)

        # Table names matching InvestmentHelper convention
        self.prices_table = _get_table_name('prices')
        self.watchlist_table = _get_table_name('watchlist')
    
    def save_etf(self, ticker: str, price_info: Dict[str, Any], source: str) -> None:
        """Save or update an ETF record using PynamoDB.

        Preserves existing metadata fields (created_at, risk ranges, etc.)
        when updating an existing record.

        Args:
            ticker: ETF symbol (e.g., 'SPY')
            price_info: Dict with regularMarketPrice, regularMarketOpen, shortName, etc.
            source: Data source name (e.g., 'yfinance')
        """
        try:
            # Try to load existing record to preserve metadata
            etf = ETF.get(ticker)
            etf.current_price = price_info.get('regularMarketPrice')
            open_price = price_info.get('regularMarketOpen')
            if open_price:
                etf.open_price = open_price
            name = price_info.get('shortName') or price_info.get('longName')
            if name:
                etf.name = name
            etf.updated_at = datetime.now(timezone.utc)
            etf.save()
        except DoesNotExist:
            # Create new record
            etf = ETF(
                ticker=ticker,
                current_price=price_info.get('regularMarketPrice'),
                open_price=price_info.get('regularMarketOpen'),
                name=price_info.get('shortName') or price_info.get('longName'),
            )
            etf.save()
        except Exception as e:
            logger.error("Error saving ETF: %s", e, extra={'ticker': ticker, 'source': source})
            raise

    def save_etf_history(self, ticker: str, history_items: List[Dict[str, Any]]) -> None:
        """Save ETF history records using PynamoDB batch write.

        Each item becomes a separate row in the etf_history table.
        Idempotent — same (ticker, date) composite key overwrites safely.

        Args:
            ticker: ETF symbol
            history_items: List of OHLCV dicts with keys:
                date, open, high, low, close, volume, adjusted_close
        """
        try:
            with ETFHistory.batch_write() as batch:
                for item in history_items:
                    date_str = item.get('date', '')
                    # Normalize date to YYYY-MM-DD (strip time portion if present)
                    if 'T' in date_str:
                        date_str = date_str.split('T')[0]
                    elif ' ' in date_str:
                        date_str = date_str.split(' ')[0]

                    # Skip items with missing required fields
                    close_val = item.get('close')
                    if close_val is None or not date_str:
                        continue

                    # Handle NaN/Infinity values
                    def safe_num(val):
                        if val is None:
                            return None
                        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                            return None
                        return val

                    open_val = safe_num(item.get('open'))
                    high_val = safe_num(item.get('high'))
                    low_val = safe_num(item.get('low'))
                    close_val = safe_num(close_val)
                    volume_val = safe_num(item.get('volume'))

                    if close_val is None:
                        continue

                    record = ETFHistory(
                        ticker=ticker,
                        date=date_str,
                        open_price=open_val or 0,
                        high_price=high_val or 0,
                        low_price=low_val or 0,
                        close_price=close_val,
                        volume=volume_val or 0,
                        adjusted_close=safe_num(item.get('adjusted_close')),
                    )
                    batch.save(record)
            logger.info("Saved %d history records", len(history_items), extra={'ticker': ticker})
        except Exception as e:
            logger.error("Error saving ETF history: %s", e, extra={'ticker': ticker})
            raise

    # =========================================================================
    # Watchlist Methods
    # =========================================================================

    def get_watchlist_symbols(
        self,
        enabled_only: bool = True,
        symbol_type: Optional[str] = None
    ) -> List[str]:
        """Get symbols from the watchlist table.

        Args:
            enabled_only: If True, only return enabled symbols (default: True)
            symbol_type: Filter by symbol type ('equity', 'etf', 'index', etc.)

        Returns:
            List of symbol strings, sorted by priority (lower = higher priority)
        """
        table_name = self.watchlist_table
        try:
            table = self.dynamodb.Table(table_name)
            items = []

            # Build filter expression
            filter_parts = []
            expression_values = {}

            if enabled_only:
                filter_parts.append("enabled = :enabled")
                expression_values[":enabled"] = True

            if symbol_type:
                filter_parts.append("symbol_type = :symbol_type")
                expression_values[":symbol_type"] = symbol_type

            scan_kwargs = {}
            if filter_parts:
                scan_kwargs["FilterExpression"] = " AND ".join(filter_parts)
                scan_kwargs["ExpressionAttributeValues"] = expression_values

            response = table.scan(**scan_kwargs)
            items.extend(response.get('Items', []))

            while 'LastEvaluatedKey' in response:
                scan_kwargs["ExclusiveStartKey"] = response['LastEvaluatedKey']
                response = table.scan(**scan_kwargs)
                items.extend(response.get('Items', []))

            # Sort by priority (default to 100 if not set)
            items.sort(key=lambda x: x.get('priority', 100))

            return [item['symbol'] for item in items if 'symbol' in item]

        except ClientError as e:
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error("Error getting watchlist symbols: %s", error_msg, extra={'table': table_name})
            raise

    def get_watchlist_item(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get a single watchlist item by symbol.

        Args:
            symbol: The symbol to retrieve

        Returns:
            Dict with watchlist item data, or None if not found
        """
        table_name = self.watchlist_table
        try:
            table = self.dynamodb.Table(table_name)
            response = table.get_item(Key={'symbol': symbol})
            return response.get('Item')
        except ClientError as e:
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error("Error getting watchlist item: %s", error_msg, extra={'symbol': symbol})
            return None

    def add_watchlist_symbol(
        self,
        symbol: str,
        symbol_type: str = 'equity',
        enabled: bool = True,
        priority: int = 100,
        added_by: str = 'manual',
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add a symbol to the watchlist.

        Args:
            symbol: Ticker symbol (e.g., 'SPY', '^VIX')
            symbol_type: Type of symbol ('equity', 'etf', 'index', 'commodity')
            enabled: Whether to fetch prices for this symbol
            priority: Fetch order (lower = higher priority)
            added_by: Source ('manual', 'api', 'migration')
            metadata: Optional additional data (name, exchange, etc.)

        Returns:
            True if successful
        """
        from datetime import datetime
        table_name = self.watchlist_table

        item = {
            'symbol': symbol.upper(),
            'symbol_type': symbol_type,
            'enabled': enabled,
            'priority': priority,
            'added_at': datetime.now().isoformat(),
            'added_by': added_by,
        }
        if metadata:
            item['metadata'] = metadata

        try:
            table = self.dynamodb.Table(table_name)
            table.put_item(Item=item)
            logger.info("Added symbol to watchlist", extra={'symbol': symbol, 'type': symbol_type})
            return True
        except ClientError as e:
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error("Error adding to watchlist: %s", error_msg, extra={'symbol': symbol})
            raise

    def update_watchlist_symbol(
        self,
        symbol: str,
        enabled: Optional[bool] = None,
        priority: Optional[int] = None
    ) -> bool:
        """Update a watchlist symbol's enabled status or priority.

        Args:
            symbol: The symbol to update
            enabled: New enabled status (optional)
            priority: New priority (optional)

        Returns:
            True if successful
        """
        table_name = self.watchlist_table

        update_parts = []
        expression_values = {}
        expression_names = {}

        if enabled is not None:
            update_parts.append("#enabled = :enabled")
            expression_values[":enabled"] = enabled
            expression_names["#enabled"] = "enabled"

        if priority is not None:
            update_parts.append("priority = :priority")
            expression_values[":priority"] = priority

        if not update_parts:
            return True  # Nothing to update

        try:
            table = self.dynamodb.Table(table_name)
            update_kwargs = {
                "Key": {"symbol": symbol.upper()},
                "UpdateExpression": "SET " + ", ".join(update_parts),
                "ExpressionAttributeValues": expression_values,
            }
            if expression_names:
                update_kwargs["ExpressionAttributeNames"] = expression_names

            table.update_item(**update_kwargs)
            logger.info("Updated watchlist symbol", extra={'symbol': symbol})
            return True
        except ClientError as e:
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error("Error updating watchlist: %s", error_msg, extra={'symbol': symbol})
            raise

    def remove_watchlist_symbol(self, symbol: str) -> bool:
        """Remove a symbol from the watchlist.

        Args:
            symbol: The symbol to remove

        Returns:
            True if successful
        """
        table_name = self.watchlist_table
        try:
            table = self.dynamodb.Table(table_name)
            table.delete_item(Key={'symbol': symbol.upper()})
            logger.info("Removed symbol from watchlist", extra={'symbol': symbol})
            return True
        except ClientError as e:
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error("Error removing from watchlist: %s", error_msg, extra={'symbol': symbol})
            raise

    def get_all_watchlist_items(self) -> List[Dict[str, Any]]:
        """Get all items from the watchlist table.

        Returns:
            List of all watchlist items
        """
        table_name = self.watchlist_table
        try:
            table = self.dynamodb.Table(table_name)
            items = []
            response = table.scan()
            items.extend(response.get('Items', []))
            while 'LastEvaluatedKey' in response:
                response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                items.extend(response.get('Items', []))
            return items
        except ClientError as e:
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error("Error scanning watchlist: %s", error_msg, extra={'table': table_name})
            raise

    def get_price_timestamps(self, symbols: List[str]) -> Dict[str, Optional[str]]:
        """Get updated_at timestamps for a list of symbols from the prices table.

        Args:
            symbols: List of ETF symbols to query

        Returns:
            Dict mapping symbol to updated_at timestamp (ISO 8601) or None if not found
        """
        try:
            result: Dict[str, Optional[str]] = {symbol: None for symbol in symbols}

            for etf in ETF.scan(attributes_to_get=['ticker', 'updated_at']):
                ticker = etf.ticker
                if ticker in result and etf.updated_at:
                    result[ticker] = etf.updated_at.isoformat()

            return result
        except Exception as e:
            logger.error("Error getting price timestamps: %s", e)
            return {symbol: None for symbol in symbols}

    def get_price_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get full price data for a single symbol from the prices table.

        Args:
            symbol: ETF symbol to query

        Returns:
            Dict with all price data fields, or None if not found
        """
        try:
            etf = ETF.get(symbol)
            return {
                'ticker': etf.ticker,
                'name': etf.name,
                'current_price': float(etf.current_price) if etf.current_price is not None else None,
                'open_price': float(etf.open_price) if etf.open_price is not None else None,
                'updated_at': etf.updated_at.isoformat() if etf.updated_at else None,
            }
        except DoesNotExist:
            return None
        except Exception as e:
            logger.error("Error getting price data: %s", e, extra={'symbol': symbol})
            return None

    def get_all_price_records(self) -> List[Dict[str, Any]]:
        """Get all records from the prices table.

        Returns:
            List of all price records with ticker, updated_at
        """
        try:
            items = []
            for etf in ETF.scan(attributes_to_get=['ticker', 'updated_at']):
                items.append({
                    'ticker': etf.ticker,
                    'updated_at': etf.updated_at.isoformat() if etf.updated_at else None,
                })
            return items
        except Exception as e:
            logger.error("Error getting all price records: %s", e)
            return []