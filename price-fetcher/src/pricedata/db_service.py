"""
DynamoDB service for price data storage.

This module provides low-level DynamoDB operations for the pricedata package.
"""

import logging
import os
import boto3
from botocore.exceptions import ClientError
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


def _get_default_table_name() -> str:
    """
    Get default table name matching InvestmentHelper convention.

    Returns:
        Table name (default: 'etfs')
    """
    return 'etfs'


class DBService:
    """DynamoDB service for reading and writing price data."""

    def __init__(
        self,
        table_name: Optional[str] = None,
        region_name: Optional[str] = None
    ):
        """
        Initialize DynamoDB connection.

        Args:
            table_name: DynamoDB table name. Defaults to PRICES_TABLE env var
                       or 'etfs'.
            region_name: AWS region. Defaults to AWS_REGION env var or 'us-east-1'.
        """
        self.region = region_name or os.getenv('AWS_REGION', 'us-east-1')
        self.table_name = table_name or os.getenv(
            'PRICES_TABLE', _get_default_table_name()
        )
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self._table = None

    @property
    def table(self):
        """Lazy-load table reference."""
        if self._table is None:
            self._table = self.dynamodb.Table(self.table_name)
        return self._table

    def get_price_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get full price data for a single symbol.

        Args:
            symbol: ETF/stock symbol (e.g., "AAPL")

        Returns:
            Dict with all price data fields, or None if not found
        """
        try:
            response = self.table.get_item(Key={'ticker': symbol})
            return response.get('Item')
        except ClientError as e:
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error("Error getting price data: %s", error_msg, extra={'symbol': symbol})
            return None
        except Exception as e:
            logger.error("Unexpected error getting price data: %s", e, extra={'symbol': symbol})
            return None

    def get_all_price_records(self) -> List[Dict[str, Any]]:
        """
        Get all price records from the table.

        Returns:
            List of price records with symbol, timestamps, and source info
        """
        try:
            items = []
            response = self.table.scan(
                ProjectionExpression='ticker, updated_at, current_price'
            )
            items.extend(response.get('Items', []))

            while 'LastEvaluatedKey' in response:
                response = self.table.scan(
                    ProjectionExpression='ticker, updated_at, current_price',
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                items.extend(response.get('Items', []))

            return items
        except ClientError as e:
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error("Error scanning price records: %s", error_msg)
            return []
        except Exception as e:
            logger.error("Unexpected error scanning price records: %s", e)
            return []

    def put_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Write a price record to the table.

        Args:
            item: Price record with etf_symbol key and price data

        Returns:
            DynamoDB response

        Raises:
            ClientError: If DynamoDB operation fails
        """
        try:
            response = self.table.put_item(Item=item)
            return response
        except ClientError as e:
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error("Error putting item: %s", error_msg)
            raise
        except Exception as e:
            logger.error("Unexpected error putting item: %s", e)
            raise
