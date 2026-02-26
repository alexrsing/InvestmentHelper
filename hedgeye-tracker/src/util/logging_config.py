"""
Logging configuration for hedgeye-tracker.

Provides consistent logging setup for both Lambda (JSON format for CloudWatch)
and CLI (human-readable format) contexts.

Usage:
    from util.logging_config import setup_logging, get_logger

    setup_logging()  # Auto-detects Lambda vs CLI
    logger = get_logger(__name__)

    logger.info("Processing symbol", extra={'symbol': 'AAPL'})
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class JsonFormatter(logging.Formatter):
    """Format log records as JSON for CloudWatch Insights queries."""

    EXCLUDE_FIELDS = {
        'name', 'msg', 'args', 'created', 'filename', 'funcName',
        'levelname', 'levelno', 'lineno', 'module', 'msecs',
        'pathname', 'process', 'processName', 'relativeCreated',
        'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
        'taskName', 'message'
    }

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            'timestamp': datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(timespec='milliseconds'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in self.EXCLUDE_FIELDS and key not in log_obj:
                try:
                    json.dumps(value)
                    log_obj[key] = value
                except (TypeError, ValueError):
                    log_obj[key] = str(value)

        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


class HumanFormatter(logging.Formatter):
    """Human-readable formatter for CLI output."""

    LEVEL_COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m',
    }
    RESET = '\033[0m'

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')

        level = record.levelname.ljust(5)
        if self.use_colors:
            color = self.LEVEL_COLORS.get(record.levelname, '')
            level = f"{color}{level}{self.RESET}"

        logger_name = record.name

        message = record.getMessage()

        extras = []
        for key, value in record.__dict__.items():
            if key not in JsonFormatter.EXCLUDE_FIELDS and key not in {'timestamp', 'level', 'logger', 'message'}:
                extras.append(f"{key}={value}")

        extra_str = f" ({', '.join(extras)})" if extras else ""

        output = f"{timestamp} {level} [{logger_name}] {message}{extra_str}"

        if record.exc_info:
            output += f"\n{self.formatException(record.exc_info)}"

        return output


def setup_logging(
    json_format: Optional[bool] = None,
    level: Optional[str] = None,
    logger_name: Optional[str] = None
) -> None:
    """Configure logging for the application."""
    if json_format is None:
        json_format = 'AWS_LAMBDA_FUNCTION_NAME' in os.environ

    if level is None:
        level = os.getenv('LOG_LEVEL', 'INFO').upper()

    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level, logging.INFO))

    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(getattr(logging, level, logging.INFO))

    if json_format:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(HumanFormatter())

    logger.addHandler(handler)

    if logger_name:
        logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
