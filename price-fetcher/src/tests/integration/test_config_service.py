"""
Integration tests for ConfigService DynamoDB configuration storage.

Tests cover:
- put_config / get_config round-trip
- TTL attribute setting
- list_configs (query by type)
- delete_config
- LRU cache behavior
- Cache invalidation

Issue: #66
"""

import os
import sys
import time

import boto3
import pytest
from moto import mock_aws

# Add fetchers to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'fetchers'))

from tests.integration.helpers import TEST_CONFIG_TABLE, setup_test_environment


@pytest.fixture
def config_table(aws_credentials, monkeypatch):
    """Create mocked DynamoDB config table."""
    setup_test_environment()

    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

        # Create config table with new marketdata-{env}-config naming
        table = dynamodb.create_table(
            TableName=TEST_CONFIG_TABLE,
            KeySchema=[
                {'AttributeName': 'config_type', 'KeyType': 'HASH'},
                {'AttributeName': 'config_key', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'config_type', 'AttributeType': 'S'},
                {'AttributeName': 'config_key', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        table.meta.client.get_waiter('table_exists').wait(
            TableName=TEST_CONFIG_TABLE
        )

        yield table


class TestConfigPutGet:
    """Test storing and retrieving configuration."""

    def test_config_put_get(self, config_table, monkeypatch):
        """Store and retrieve config by type/key."""
        # Reset singleton
        import config_service
        config_service._config_service = None

        svc = config_service.ConfigService()

        # Store config
        test_data = {
            'holidays': [
                {'atDate': '2026-01-20', 'eventName': 'MLK Day'},
                {'atDate': '2026-02-17', 'eventName': 'Presidents Day'},
            ]
        }
        svc.put_config('holidays', 'US', test_data)

        # Retrieve config
        result = svc.get_config('holidays', 'US')

        assert result is not None
        assert 'holidays' in result
        assert len(result['holidays']) == 2
        assert result['holidays'][0]['eventName'] == 'MLK Day'

    def test_config_get_not_found(self, config_table, monkeypatch):
        """Non-existent config returns None."""
        import config_service
        config_service._config_service = None

        svc = config_service.ConfigService()

        result = svc.get_config('nonexistent', 'key')

        assert result is None

    def test_config_default_key(self, config_table, monkeypatch):
        """Config with default key works."""
        import config_service
        config_service._config_service = None

        svc = config_service.ConfigService()

        svc.put_config('settings', 'default', {'debug': True})
        result = svc.get_config('settings')  # Uses default key

        assert result == {'debug': True}


class TestConfigTTL:
    """Test TTL attribute setting."""

    def test_config_ttl(self, config_table, monkeypatch):
        """Config with TTL attribute set correctly."""
        import config_service
        config_service._config_service = None

        svc = config_service.ConfigService()

        # Store with 1 hour TTL
        svc.put_config('cache', 'temp', {'value': 123}, ttl_seconds=3600)

        # Verify TTL was set
        response = config_table.get_item(
            Key={'config_type': 'cache', 'config_key': 'temp'}
        )
        item = response.get('Item')

        assert item is not None
        assert 'ttl' in item
        # TTL should be approximately current time + 3600
        expected_ttl = int(time.time()) + 3600
        assert abs(item['ttl'] - expected_ttl) < 10  # Within 10 seconds

    def test_config_no_ttl(self, config_table, monkeypatch):
        """Config without TTL has no ttl attribute."""
        import config_service
        config_service._config_service = None

        svc = config_service.ConfigService()

        svc.put_config('permanent', 'config', {'value': 456})

        response = config_table.get_item(
            Key={'config_type': 'permanent', 'config_key': 'config'}
        )
        item = response.get('Item')

        assert item is not None
        assert 'ttl' not in item


class TestConfigListByType:
    """Test listing config keys by type."""

    def test_config_list_by_type(self, config_table, monkeypatch):
        """Query all keys for a given type."""
        import config_service
        config_service._config_service = None

        svc = config_service.ConfigService()

        # Store multiple configs of same type
        svc.put_config('holidays', 'US', {'holidays': []})
        svc.put_config('holidays', 'UK', {'holidays': []})
        svc.put_config('holidays', 'JP', {'holidays': []})
        svc.put_config('settings', 'default', {'debug': False})

        # List only holidays
        result = svc.list_configs('holidays')

        assert len(result) == 3
        keys = [item['config_key'] for item in result]
        assert set(keys) == {'US', 'UK', 'JP'}

    def test_config_list_by_type_empty(self, config_table, monkeypatch):
        """Empty result for type with no configs."""
        import config_service
        config_service._config_service = None

        svc = config_service.ConfigService()

        result = svc.list_configs('nonexistent_type')

        assert result == []


class TestConfigDelete:
    """Test config deletion."""

    def test_config_delete(self, config_table, monkeypatch):
        """Remove config entry."""
        import config_service
        config_service._config_service = None

        svc = config_service.ConfigService()

        # Create then delete
        svc.put_config('temp', 'to_delete', {'data': 'test'})
        assert svc.get_config('temp', 'to_delete') is not None

        svc.delete_config('temp', 'to_delete')
        assert svc.get_config('temp', 'to_delete') is None

    def test_config_delete_nonexistent(self, config_table, monkeypatch):
        """Delete nonexistent config doesn't raise."""
        import config_service
        config_service._config_service = None

        svc = config_service.ConfigService()

        # Should not raise
        svc.delete_config('nonexistent', 'key')


class TestConfigCache:
    """Test LRU cache behavior."""

    def test_config_cache_hit(self, config_table, monkeypatch):
        """Second get uses LRU cache (no DynamoDB call)."""
        import config_service
        config_service._config_service = None
        config_service.clear_config_cache()

        # Store config
        svc = config_service.ConfigService()
        svc.put_config('cached', 'test', {'value': 'original'})

        # First call - goes to DynamoDB
        result1 = config_service.get_cached_config('cached', 'test')
        assert result1 == {'value': 'original'}

        # Modify in DynamoDB directly
        config_table.put_item(Item={
            'config_type': 'cached',
            'config_key': 'test',
            'data': {'value': 'modified'},
            'updated_at': '2026-01-31T12:00:00+00:00'
        })

        # Second call - should still return cached value
        result2 = config_service.get_cached_config('cached', 'test')
        assert result2 == {'value': 'original'}  # Still cached

    def test_config_cache_invalidation(self, config_table, monkeypatch):
        """clear_config_cache() forces fresh read."""
        import config_service
        config_service._config_service = None
        config_service.clear_config_cache()

        # Store config
        svc = config_service.ConfigService()
        svc.put_config('cached', 'invalidate', {'value': 'first'})

        # First call
        result1 = config_service.get_cached_config('cached', 'invalidate')
        assert result1 == {'value': 'first'}

        # Modify in DynamoDB
        svc.put_config('cached', 'invalidate', {'value': 'second'})

        # Clear cache
        config_service.clear_config_cache()

        # Should now get new value
        result2 = config_service.get_cached_config('cached', 'invalidate')
        assert result2 == {'value': 'second'}


class TestConfigUpdatedAt:
    """Test updated_at timestamp."""

    def test_config_updated_at_set(self, config_table, monkeypatch):
        """put_config sets updated_at timestamp."""
        import config_service
        config_service._config_service = None

        svc = config_service.ConfigService()
        svc.put_config('timestamp', 'test', {'data': 'value'})

        response = config_table.get_item(
            Key={'config_type': 'timestamp', 'config_key': 'test'}
        )
        item = response.get('Item')

        assert item is not None
        assert 'updated_at' in item
        # Should be a valid ISO timestamp
        assert 'T' in item['updated_at']
        assert '+' in item['updated_at'] or 'Z' in item['updated_at']
