"""Database service module for putting security range data into the database"""

import os
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from util.logging_config import get_logger

logger = get_logger(__name__)


class DatabaseService:
    def __init__(self, region_name: Optional[str] = None):
        region = region_name or os.environ.get("AWS_REGION") or os.environ.get("AWS_REGION_NAME", "us-east-1")
        self.dynamodb: Any = boto3.resource("dynamodb", region_name=region)
        self.client: Any = boto3.client("dynamodb", region_name=region)

    def put_item(self, table_name: str, item: Dict[str, Any]) -> bool:
        """Put a single item into DynamoDB table."""
        try:
            table = self.dynamodb.Table(table_name)
            response: bool = table.put_item(Item=item)
            return response
        except ClientError as e:
            logger.error("Error putting item to %s: %s", table_name, e)
            raise
        except Exception as e:
            logger.error("Unexpected error putting item to %s: %s", table_name, e)
            raise

    def batch_put_items(self, table_name: str, items: List[Dict[str, Any]]) -> bool:
        """
        Put multiple items into DynamoDB table using batch writer.
        Break into chunks of 25 items if necessary.
        """
        try:
            table = self.dynamodb.Table(table_name)
            with table.batch_writer() as batch:
                for item in items:
                    batch.put_item(Item=item)
            return True
        except ClientError as e:
            logger.error("Error batch putting items to %s: %s", table_name, e)
            raise
        except Exception as e:
            logger.error("Unexpected error batch putting items to %s: %s", table_name, e)
            raise

    def get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get a single item from DynamoDB table by key."""
        try:
            table = self.dynamodb.Table(table_name)
            response = table.get_item(Key=key)
            return response.get("Item")
        except ClientError as e:
            logger.error("Error getting item from %s: %s", table_name, e)
            raise
        except Exception as e:
            logger.error("Unexpected error getting item from %s: %s", table_name, e)
            raise

    def save_item_with_history(
        self,
        table_name: str,
        etf_symbol: str,
        current_data: Dict[str, Any],
        history: List[Dict[str, Any]],
        history_field: str,
    ) -> bool:
        """
        Save an item with complete history list.

        Args:
            table_name: Name of the DynamoDB table
            etf_symbol: ETF symbol (primary key)
            current_data: Current data to store (flat attributes)
            history: Complete list of historical entries
            history_field: Name of the history field (e.g., 'trade_history' or 'trend_history')

        Returns:
            True if successful
        """
        try:
            table = self.dynamodb.Table(table_name)

            # Create or replace item with full history
            new_item = {"etf_symbol": etf_symbol, **current_data, history_field: history}
            table.put_item(Item=new_item)

            return True
        except ClientError as e:
            logger.error("Error saving item with history to %s: %s", table_name, e)
            raise
        except Exception as e:
            logger.error("Unexpected error saving item with history to %s: %s", table_name, e)
            raise

    def upsert_item_with_history(
        self,
        table_name: str,
        etf_symbol: str,
        current_data: Dict[str, Any],
        history_entry: Dict[str, Any],
        history_field: str,
    ) -> bool:
        """
        Upsert an item with history tracking.

        Args:
            table_name: Name of the DynamoDB table
            etf_symbol: ETF symbol (primary key)
            current_data: Current data to store (flat attributes)
            history_entry: New history entry to append
            history_field: Name of the history field (e.g., 'trade_history' or 'trend_history')

        Returns:
            True if successful
        """
        try:
            table = self.dynamodb.Table(table_name)

            # Check if item already exists
            existing_item = self.get_item(table_name, {"etf_symbol": etf_symbol})

            if existing_item:
                # Item exists - update it and append to history
                # Build update expression
                update_parts = []
                expression_values = {}
                expression_names = {}

                # Update current data fields
                for key, value in current_data.items():
                    if key != "etf_symbol":  # Don't update the primary key
                        safe_key = f"#{key}"
                        value_key = f":{key}"
                        update_parts.append(f"{safe_key} = {value_key}")
                        expression_values[value_key] = value
                        expression_names[safe_key] = key

                # Append to history list
                history_key = f"#{history_field}"
                history_value_key = f":{history_field}"
                update_parts.append(
                    f"{history_key} = list_append(if_not_exists({history_key}, :empty_list), {history_value_key})"
                )
                expression_values[history_value_key] = [history_entry]
                expression_values[":empty_list"] = []
                expression_names[history_key] = history_field

                update_expression = "SET " + ", ".join(update_parts)

                table.update_item(
                    Key={"etf_symbol": etf_symbol},
                    UpdateExpression=update_expression,
                    ExpressionAttributeValues=expression_values,
                    ExpressionAttributeNames=expression_names,
                )
            else:
                # Item doesn't exist - create new one
                new_item = {"etf_symbol": etf_symbol, **current_data, history_field: [history_entry]}
                table.put_item(Item=new_item)

            return True
        except ClientError as e:
            logger.error("Error upserting item with history to %s: %s", table_name, e)
            raise
        except Exception as e:
            logger.error("Unexpected error upserting item with history to %s: %s", table_name, e)
            raise
