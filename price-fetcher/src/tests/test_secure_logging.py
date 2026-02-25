"""Tests for secure logging utilities."""

import logging
import pytest
from pricedata.secure_logging import (
    mask_api_key,
    mask_secret_name,
    safe_log_config,
    get_logger,
    log_api_call,
    redact_url,
)


class TestMaskApiKey:
    """Tests for mask_api_key function."""

    def test_masks_long_key(self):
        """Should show first 4 chars and mask the rest."""
        assert mask_api_key("abc123xyz789") == "abc1********"

    def test_masks_with_custom_visible_chars(self):
        """Should respect visible_chars parameter."""
        assert mask_api_key("abc123xyz789", visible_chars=6) == "abc123********"

    def test_short_key_fully_masked(self):
        """Keys shorter than visible_chars should be fully masked."""
        assert mask_api_key("abc") == "****"
        assert mask_api_key("abcd") == "****"

    def test_none_returns_masked(self):
        """None should return masked string."""
        assert mask_api_key(None) == "****"

    def test_empty_string_returns_masked(self):
        """Empty string should return masked string."""
        assert mask_api_key("") == "****"


class TestMaskSecretName:
    """Tests for mask_secret_name function."""

    def test_masks_three_part_path(self):
        """Should shorten three-part paths."""
        result = mask_secret_name("dev/price-fetcher/alpha-vantage-api-key")
        assert result == "dev/.../alpha-vantage-api-key"

    def test_masks_longer_path(self):
        """Should work with paths longer than 3 parts."""
        result = mask_secret_name("aws/dev/app/secrets/api-key")
        assert result == "aws/.../api-key"

    def test_preserves_short_path(self):
        """Short paths should be preserved."""
        assert mask_secret_name("simple-secret") == "simple-secret"
        assert mask_secret_name("env/secret") == "env/secret"

    def test_none_returns_masked(self):
        """None should return masked string."""
        assert mask_secret_name(None) == "****"

    def test_empty_string_returns_empty(self):
        """Empty string should return masked string."""
        assert mask_secret_name("") == "****"


class TestSafeLogConfig:
    """Tests for safe_log_config function."""

    def test_masks_api_key(self):
        """Should mask keys containing 'key'."""
        config = {"api_key": "secret123", "region": "us-west-2"}
        result = safe_log_config(config)
        assert result["api_key"] == "secr********"
        assert result["region"] == "us-west-2"

    def test_masks_multiple_sensitive_keys(self):
        """Should mask all sensitive patterns."""
        config = {
            "api_key": "key123",
            "secret_value": "secret123",
            "password": "pass123",
            "auth_token": "token123",
            "credential": "cred123",
            "normal_field": "visible",
        }
        result = safe_log_config(config)
        assert "********" in result["api_key"]
        assert "********" in result["secret_value"]
        assert "********" in result["password"]
        assert "********" in result["auth_token"]
        assert "********" in result["credential"]
        assert result["normal_field"] == "visible"

    def test_handles_none_values(self):
        """Should handle None values gracefully."""
        config = {"api_key": None, "region": "us-west-2"}
        result = safe_log_config(config)
        assert result["api_key"] is None
        assert result["region"] == "us-west-2"

    def test_case_insensitive(self):
        """Should match patterns case-insensitively."""
        config = {"API_KEY": "secret123", "ApiKey": "secret456"}
        result = safe_log_config(config)
        assert "********" in result["API_KEY"]
        assert "********" in result["ApiKey"]

    def test_original_dict_unchanged(self):
        """Should not modify the original dictionary."""
        config = {"api_key": "secret123"}
        safe_log_config(config)
        assert config["api_key"] == "secret123"


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger(self):
        """Should return a logger instance."""
        logger = get_logger("test")
        assert isinstance(logger, logging.Logger)

    def test_logger_has_handler(self):
        """Logger should have at least one handler."""
        logger = get_logger("test_handler")
        assert len(logger.handlers) >= 1

    def test_same_logger_returned(self):
        """Same name should return same logger."""
        logger1 = get_logger("test_same")
        logger2 = get_logger("test_same")
        assert logger1 is logger2


class TestLogApiCall:
    """Tests for log_api_call function."""

    def test_logs_success(self, caplog):
        """Should log successful API calls at INFO level."""
        logger = logging.getLogger("test_api_success")
        logger.setLevel(logging.INFO)

        with caplog.at_level(logging.INFO):
            log_api_call(logger, "AlphaVantage", "/query", success=True)

        assert "AlphaVantage" in caplog.text
        assert "SUCCESS" in caplog.text

    def test_logs_failure(self, caplog):
        """Should log failed API calls at WARNING level."""
        logger = logging.getLogger("test_api_failure")
        logger.setLevel(logging.WARNING)

        with caplog.at_level(logging.WARNING):
            log_api_call(logger, "AlphaVantage", "/query", success=False)

        assert "FAILED" in caplog.text

    def test_includes_duration(self, caplog):
        """Should include duration when provided."""
        logger = logging.getLogger("test_api_duration")
        logger.setLevel(logging.INFO)

        with caplog.at_level(logging.INFO):
            log_api_call(logger, "API", "/endpoint", success=True, duration_ms=150.5)

        assert "150ms" in caplog.text or "151ms" in caplog.text

    def test_logs_error_type_not_message(self, caplog):
        """Should log error type but not the full message."""
        logger = logging.getLogger("test_api_error")
        logger.setLevel(logging.WARNING)

        error = ValueError("API key invalid: secret123")

        with caplog.at_level(logging.WARNING):
            log_api_call(logger, "API", "/endpoint", success=False, error=error)

        assert "ValueError" in caplog.text
        assert "secret123" not in caplog.text


class TestRedactUrl:
    """Tests for redact_url function."""

    def test_redacts_apikey(self):
        """Should redact apikey parameter."""
        url = "https://api.example.com?apikey=secret123&symbol=AAPL"
        result = redact_url(url)
        assert "secret123" not in result
        assert "[REDACTED]" in result
        assert "symbol=AAPL" in result

    def test_redacts_api_key_underscore(self):
        """Should redact api_key parameter."""
        url = "https://api.example.com?api_key=secret123"
        result = redact_url(url)
        assert "secret123" not in result
        assert "[REDACTED]" in result

    def test_redacts_token(self):
        """Should redact token parameter."""
        url = "https://api.example.com?token=mytoken123"
        result = redact_url(url)
        assert "mytoken123" not in result
        assert "[REDACTED]" in result

    def test_redacts_multiple_params(self):
        """Should redact multiple sensitive parameters."""
        url = "https://api.example.com?apikey=key1&token=token1&data=safe"
        result = redact_url(url)
        assert "key1" not in result
        assert "token1" not in result
        assert "data=safe" in result

    def test_case_insensitive(self):
        """Should match parameters case-insensitively."""
        url = "https://api.example.com?APIKEY=secret123"
        result = redact_url(url)
        assert "secret123" not in result

    def test_none_returns_masked(self):
        """None should return masked string."""
        assert redact_url(None) == "****"

    def test_empty_returns_masked(self):
        """Empty string should return masked string."""
        assert redact_url("") == "****"

    def test_url_without_sensitive_params(self):
        """URLs without sensitive params should be unchanged."""
        url = "https://api.example.com?symbol=AAPL&date=2024-01-01"
        result = redact_url(url)
        assert result == url
