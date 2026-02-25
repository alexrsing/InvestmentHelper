"""
Integration tests for API key loading from single JSON secret and environment variables.

Tests cover:
- Loading API keys from Secrets Manager (single JSON secret)
- Loading tier config from the same secret
- Fallback to environment variables
- Placeholder value rejection
- Missing key handling
- Cache behavior

Issue: #71
"""

import json
import os
import sys

import boto3
import pytest
from moto import mock_aws

# Add fetchers to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'fetchers'))


class TestAPIKeyFromSecretsManager:
    """Test loading API keys from single JSON secret in Secrets Manager."""

    @mock_aws
    def test_api_key_from_secrets_manager(self, monkeypatch, aws_credentials):
        """Load API key from JSON secret when in Lambda environment."""
        # Create JSON secret in mocked Secrets Manager
        client = boto3.client('secretsmanager', region_name='us-west-2')
        client.create_secret(
            Name='test/price-fetcher/config',
            SecretString=json.dumps({
                "ALPHA_VANTAGE_API_KEY": "test-api-key-from-sm",
                "ALPHA_VANTAGE_TIER": "free",
            })
        )

        # Simulate Lambda environment
        monkeypatch.setenv('PRICE_FETCHER_SECRET_NAME', 'test/price-fetcher/config')
        monkeypatch.setenv('AWS_LAMBDA_FUNCTION_NAME', 'test-price-fetcher')

        import api_keys
        api_keys.clear_cache()

        key = api_keys.get_api_key('ALPHA_VANTAGE_API_KEY')
        assert key == 'test-api-key-from-sm'

    @mock_aws
    def test_tier_from_secrets_manager(self, monkeypatch, aws_credentials):
        """Load tier config from JSON secret."""
        client = boto3.client('secretsmanager', region_name='us-west-2')
        client.create_secret(
            Name='test/price-fetcher/config',
            SecretString=json.dumps({
                "FMP_API_KEY": "test-fmp-key",
                "FMP_TIER": "starter",
            })
        )

        monkeypatch.setenv('PRICE_FETCHER_SECRET_NAME', 'test/price-fetcher/config')
        monkeypatch.setenv('AWS_LAMBDA_FUNCTION_NAME', 'test-price-fetcher')

        import api_keys
        api_keys.clear_cache()

        tier = api_keys.get_api_key('FMP_TIER')
        assert tier == 'starter'


class TestAPIKeyFromEnvVar:
    """Test fallback to direct environment variables."""

    def test_api_key_from_env_var(self, monkeypatch):
        """Fallback to direct env var when not in Lambda."""
        monkeypatch.setenv('ALPHA_VANTAGE_API_KEY', 'direct-env-key-12345')

        import api_keys
        api_keys.clear_cache()

        key = api_keys.get_api_key('ALPHA_VANTAGE_API_KEY')
        assert key == 'direct-env-key-12345'

    def test_tier_from_env_var(self, monkeypatch):
        """Tier can be read from env var for local dev."""
        monkeypatch.setenv('FMP_TIER', 'premium')

        import api_keys
        api_keys.clear_cache()

        tier = api_keys.get_api_key('FMP_TIER')
        assert tier == 'premium'


class TestAPIKeyPlaceholderRejection:
    """Test rejection of placeholder API key values."""

    def test_api_key_placeholder_rejected(self, monkeypatch):
        """Values starting with 'your_' return None."""
        monkeypatch.setenv('ALPHA_VANTAGE_API_KEY', 'your_api_key_here')

        import api_keys
        api_keys.clear_cache()

        key = api_keys.get_api_key('ALPHA_VANTAGE_API_KEY')
        assert key is None

    def test_api_key_placeholder_your_underscore(self, monkeypatch):
        """Any value starting with 'your_' is rejected."""
        placeholders = [
            'your_key',
            'your_api_key',
            'your_secret_here',
            'your_12345',
        ]

        import api_keys

        for placeholder in placeholders:
            monkeypatch.setenv('ALPHA_VANTAGE_API_KEY', placeholder)
            api_keys.clear_cache()

            key = api_keys.get_api_key('ALPHA_VANTAGE_API_KEY')
            assert key is None, f"Placeholder '{placeholder}' should be rejected"


class TestAPIKeyMissing:
    """Test behavior when no API key is available."""

    def test_api_key_missing(self, monkeypatch):
        """No key available, returns None (no error)."""
        import api_keys
        api_keys.clear_cache()

        key = api_keys.get_api_key('ALPHA_VANTAGE_API_KEY')
        assert key is None

    def test_api_key_missing_does_not_raise(self, monkeypatch):
        """Missing key should not raise an exception."""
        import api_keys
        api_keys.clear_cache()

        key = api_keys.get_api_key('NONEXISTENT_API_KEY')
        assert key is None


class TestAPIKeyCache:
    """Test cache behavior for API keys."""

    @mock_aws
    def test_api_key_cached(self, monkeypatch, aws_credentials):
        """Second call uses cache, no additional Secrets Manager call."""
        client = boto3.client('secretsmanager', region_name='us-west-2')
        client.create_secret(
            Name='test/price-fetcher/config',
            SecretString=json.dumps({
                "TWELVEDATA_API_KEY": "cached-value-12345",
            })
        )

        monkeypatch.setenv('PRICE_FETCHER_SECRET_NAME', 'test/price-fetcher/config')
        monkeypatch.setenv('AWS_LAMBDA_FUNCTION_NAME', 'test-price-fetcher')

        import api_keys
        api_keys.clear_cache()

        # First call - loads from Secrets Manager
        key1 = api_keys.get_api_key('TWELVEDATA_API_KEY')
        assert key1 == 'cached-value-12345'

        # Second call - should use cache
        key2 = api_keys.get_api_key('TWELVEDATA_API_KEY')
        assert key2 == 'cached-value-12345'

    def test_api_key_cache_cleared(self, monkeypatch):
        """Cache can be cleared to force fresh lookup."""
        monkeypatch.setenv('FMP_API_KEY', 'original-value')

        import api_keys
        api_keys.clear_cache()

        # First call
        key1 = api_keys.get_api_key('FMP_API_KEY')
        assert key1 == 'original-value'

        # Change env var
        monkeypatch.setenv('FMP_API_KEY', 'new-value')

        # Without clearing cache, should still return original
        key2 = api_keys.get_api_key('FMP_API_KEY')
        assert key2 == 'original-value'

        # Clear cache
        api_keys.clear_cache()

        # Now should get new value
        key3 = api_keys.get_api_key('FMP_API_KEY')
        assert key3 == 'new-value'


class TestSecretsManagerPriority:
    """Test that Secrets Manager takes priority over env vars."""

    @mock_aws
    def test_secrets_manager_priority_over_env(self, monkeypatch, aws_credentials):
        """Secrets Manager value used even if env var is also set."""
        client = boto3.client('secretsmanager', region_name='us-west-2')
        client.create_secret(
            Name='test/price-fetcher/config',
            SecretString=json.dumps({
                "FINNHUB_API_KEY": "from-secrets-manager",
            })
        )

        monkeypatch.setenv('PRICE_FETCHER_SECRET_NAME', 'test/price-fetcher/config')
        monkeypatch.setenv('AWS_LAMBDA_FUNCTION_NAME', 'test-price-fetcher')
        monkeypatch.setenv('FINNHUB_API_KEY', 'from-env-var')

        import api_keys
        api_keys.clear_cache()

        # Should get Secrets Manager value, not env var
        key = api_keys.get_api_key('FINNHUB_API_KEY')
        assert key == 'from-secrets-manager'
