"""
Logging configuration for price-fetcher.

Provides consistent logging setup for both Lambda (JSON format for CloudWatch)
and CLI (human-readable format) contexts.

Usage:
    from logging_config import setup_logging, get_logger

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
    """
    Format log records as JSON for CloudWatch Insights queries.

    Output format:
    {
        "timestamp": "2024-01-15T10:30:00.000Z",
        "level": "INFO",
        "logger": "fetchers.main",
        "message": "Processing symbol",
        "symbol": "AAPL",
        ...
    }
    """

    # Fields to include from the log record
    STANDARD_FIELDS = {'timestamp', 'level', 'logger', 'message'}

    # Fields to exclude from extra data
    EXCLUDE_FIELDS = {
        'name', 'msg', 'args', 'created', 'filename', 'funcName',
        'levelname', 'levelno', 'lineno', 'module', 'msecs',
        'pathname', 'process', 'processName', 'relativeCreated',
        'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
        'taskName', 'message'
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a JSON string."""
        # Build base log object
        log_obj: Dict[str, Any] = {
            'timestamp': datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(timespec='milliseconds'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Add extra fields from the record
        for key, value in record.__dict__.items():
            if key not in self.EXCLUDE_FIELDS and key not in log_obj:
                # Only add serializable values
                try:
                    json.dumps(value)
                    log_obj[key] = value
                except (TypeError, ValueError):
                    log_obj[key] = str(value)

        # Add exception info if present
        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


class HumanFormatter(logging.Formatter):
    """
    Human-readable formatter for CLI output.

    Output format:
    2024-01-15 10:30:00 INFO  [fetchers.main] Processing symbol (symbol=AAPL)
    """

    LEVEL_COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record for human readability."""
        # Timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')

        # Level with optional color
        level = record.levelname.ljust(5)
        if self.use_colors:
            color = self.LEVEL_COLORS.get(record.levelname, '')
            level = f"{color}{level}{self.RESET}"

        # Logger name (shortened)
        logger_name = record.name
        if logger_name.startswith('fetchers.'):
            logger_name = logger_name[9:]  # Remove 'fetchers.' prefix

        # Base message
        message = record.getMessage()

        # Extra fields
        extras = []
        for key, value in record.__dict__.items():
            if key not in JsonFormatter.EXCLUDE_FIELDS and key not in {'timestamp', 'level', 'logger', 'message'}:
                extras.append(f"{key}={value}")

        extra_str = f" ({', '.join(extras)})" if extras else ""

        # Format output
        output = f"{timestamp} {level} [{logger_name}] {message}{extra_str}"

        # Add exception if present
        if record.exc_info:
            output += f"\n{self.formatException(record.exc_info)}"

        return output


def setup_logging(
    json_format: Optional[bool] = None,
    level: Optional[str] = None,
    logger_name: Optional[str] = None
) -> None:
    """
    Configure logging for the application.

    Args:
        json_format: Use JSON format (True) or human-readable (False).
                    If None, auto-detects based on AWS_LAMBDA_FUNCTION_NAME.
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Defaults to LOG_LEVEL env var or INFO.
        logger_name: Specific logger to configure. If None, configures root logger.

    Example:
        # Auto-detect (JSON in Lambda, human-readable in CLI)
        setup_logging()

        # Force JSON format
        setup_logging(json_format=True)

        # Set debug level
        setup_logging(level='DEBUG')
    """
    # Determine format
    if json_format is None:
        json_format = 'AWS_LAMBDA_FUNCTION_NAME' in os.environ

    # Determine level
    if level is None:
        level = os.getenv('LOG_LEVEL', 'INFO').upper()

    # Get the logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level, logging.INFO))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(getattr(logging, level, logging.INFO))

    # Set formatter
    if json_format:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(HumanFormatter())

    logger.addHandler(handler)

    # Prevent propagation to avoid duplicate logs
    if logger_name:
        logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name, typically __name__

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Hello", extra={'key': 'value'})
    """
    return logging.getLogger(name)
