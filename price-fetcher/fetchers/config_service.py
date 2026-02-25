"""
DynamoDB configuration service for Lambda-compatible config storage.

Manages configuration data (holidays, settings, etc.) in DynamoDB
instead of filesystem for Lambda compatibility.
"""

import os
import time
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, Optional

from logging_config import get_logger

logger = get_logger(__name__)


class ConfigService:
    """
    Manage configuration data in DynamoDB.

    Table schema:
    - config_type (partition key): Type of config (e.g., 'holidays', 'settings')
    - config_key (sort key): Specific key (e.g., 'US', 'default')
    - data: The configuration data (map/list/string)
    - updated_at: ISO timestamp of last update
    - ttl: Optional TTL for cache invalidation
    """

    def __init__(self, table_name: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize config service.

        Args:
            table_name: DynamoDB table name (defaults to CONFIG_TABLE_NAME env var)
            region: AWS region (defaults to AWS_REGION env var)
        """
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')

        # Build table name from env var or default
        if table_name:
            self.table_name = table_name
        else:
            self.table_name = os.getenv(
                'CONFIG_TABLE_NAME',
                'price_fetcher_config'
            )

        self._table = None
        self._dynamodb = None

    @property
    def dynamodb(self):
        """Lazy-load DynamoDB resource."""
        if self._dynamodb is None:
            import boto3
            self._dynamodb = boto3.resource('dynamodb', region_name=self.region)
        return self._dynamodb

    @property
    def table(self):
        """Lazy-load DynamoDB table."""
        if self._table is None:
            self._table = self.dynamodb.Table(self.table_name)
        return self._table

    def get_config(
        self,
        config_type: str,
        config_key: str = 'default'
    ) -> Optional[Dict[str, Any]]:
        """
        Get configuration by type and key.

        Args:
            config_type: Type of configuration (e.g., 'holidays')
            config_key: Specific key within type (e.g., 'US')

        Returns:
            The 'data' field from the config item, or None if not found
        """
        try:
            response = self.table.get_item(
                Key={
                    'config_type': config_type,
                    'config_key': config_key
                }
            )
            item = response.get('Item')
            if item:
                logger.debug(
                    "Retrieved config",
                    extra={'config_type': config_type, 'config_key': config_key}
                )
                return item.get('data')
            return None
        except Exception as e:
            logger.error(
                "Failed to get config: %s",
                type(e).__name__,
                extra={'config_type': config_type, 'config_key': config_key}
            )
            raise

    def put_config(
        self,
        config_type: str,
        config_key: str,
        data: Any,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Store configuration data.

        Args:
            config_type: Type of configuration
            config_key: Specific key within type
            data: Configuration data (will be stored in 'data' field)
            ttl_seconds: Optional TTL in seconds for automatic expiration
        """
        item = {
            'config_type': config_type,
            'config_key': config_key,
            'data': data,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }

        if ttl_seconds:
            item['ttl'] = int(time.time()) + ttl_seconds

        self.table.put_item(Item=item)
        logger.info(
            "Stored config",
            extra={'config_type': config_type, 'config_key': config_key}
        )

    def delete_config(self, config_type: str, config_key: str = 'default') -> None:
        """
        Delete a configuration item.

        Args:
            config_type: Type of configuration
            config_key: Specific key within type
        """
        self.table.delete_item(
            Key={
                'config_type': config_type,
                'config_key': config_key
            }
        )
        logger.info(
            "Deleted config",
            extra={'config_type': config_type, 'config_key': config_key}
        )

    def list_configs(self, config_type: str) -> list:
        """
        List all config keys for a given type.

        Args:
            config_type: Type of configuration

        Returns:
            List of config_key values for this type
        """
        try:
            response = self.table.query(
                KeyConditionExpression='config_type = :ct',
                ExpressionAttributeValues={':ct': config_type},
                ProjectionExpression='config_key, updated_at'
            )
            return response.get('Items', [])
        except Exception as e:
            logger.error(
                "Failed to list configs: %s",
                type(e).__name__,
                extra={'config_type': config_type}
            )
            return []


# Singleton instance with caching
_config_service: Optional[ConfigService] = None


def get_config_service() -> ConfigService:
    """Get singleton ConfigService instance."""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service


@lru_cache(maxsize=10)
def get_cached_config(config_type: str, config_key: str = 'default') -> Optional[Dict]:
    """
    Get config with LRU caching for Lambda efficiency.

    Caches results to avoid repeated DynamoDB reads within the same
    Lambda container invocation.

    Args:
        config_type: Type of configuration
        config_key: Specific key within type

    Returns:
        Configuration data or None
    """
    return get_config_service().get_config(config_type, config_key)


def clear_config_cache() -> None:
    """Clear the config cache (useful for testing or forced refresh)."""
    get_cached_config.cache_clear()
