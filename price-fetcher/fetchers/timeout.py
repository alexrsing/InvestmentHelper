"""
Lambda timeout monitoring and graceful exit handling.

Provides timeout-aware processing to prevent Lambda from being killed mid-operation.
"""

import os
import time
from contextlib import contextmanager
from typing import Any, Optional

from logging_config import get_logger

logger = get_logger(__name__)


class TimeoutApproaching(Exception):
    """Raised when Lambda timeout is approaching."""
    pass


class LambdaTimeoutMonitor:
    """
    Monitor remaining Lambda execution time.

    Uses Lambda context to get accurate remaining time, with fallback
    to elapsed time tracking for local testing.
    """

    def __init__(self, context: Optional[Any] = None, buffer_seconds: int = 60):
        """
        Initialize timeout monitor.

        Args:
            context: Lambda context object (has get_remaining_time_in_millis method)
            buffer_seconds: Stop processing this many seconds before timeout
        """
        self.context = context
        self.buffer_seconds = buffer_seconds
        self.start_time = time.time()

        # Get timeout from Lambda context or environment
        if context and hasattr(context, 'get_remaining_time_in_millis'):
            # In Lambda - will use context for accurate timing
            self._initial_remaining_ms = context.get_remaining_time_in_millis()
        else:
            # Local testing - use environment variable or default 15 minutes
            self._initial_remaining_ms = int(os.getenv('LAMBDA_TIMEOUT_MS', '900000'))

        logger.debug(
            "Timeout monitor initialized",
            extra={
                'buffer_seconds': buffer_seconds,
                'initial_remaining_ms': self._initial_remaining_ms,
                'has_context': context is not None
            }
        )

    @property
    def remaining_seconds(self) -> float:
        """Get remaining execution time in seconds."""
        if self.context and hasattr(self.context, 'get_remaining_time_in_millis'):
            # Use Lambda context for accurate remaining time
            return self.context.get_remaining_time_in_millis() / 1000
        else:
            # Fallback: calculate from elapsed time
            elapsed = time.time() - self.start_time
            return (self._initial_remaining_ms / 1000) - elapsed

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed execution time in seconds."""
        return time.time() - self.start_time

    @property
    def should_stop(self) -> bool:
        """Check if we should stop processing due to approaching timeout."""
        return self.remaining_seconds < self.buffer_seconds

    def check_timeout(self, operation: str = "") -> None:
        """
        Check if timeout is approaching and raise exception if so.

        Args:
            operation: Description of current operation (for logging)

        Raises:
            TimeoutApproaching: If remaining time is less than buffer
        """
        if self.should_stop:
            remaining = self.remaining_seconds
            logger.warning(
                "Timeout approaching, stopping processing",
                extra={
                    'operation': operation,
                    'remaining_seconds': round(remaining, 1),
                    'buffer_seconds': self.buffer_seconds
                }
            )
            raise TimeoutApproaching(
                f"Only {remaining:.1f}s remaining, stopping: {operation}"
            )

    def get_status(self) -> dict:
        """Get current timeout status for logging/response."""
        return {
            'elapsed_seconds': round(self.elapsed_seconds, 1),
            'remaining_seconds': round(self.remaining_seconds, 1),
            'buffer_seconds': self.buffer_seconds,
            'should_stop': self.should_stop
        }


@contextmanager
def timeout_aware_processing(
    context: Optional[Any] = None,
    buffer_seconds: int = 60
):
    """
    Context manager for timeout-aware processing.

    Usage:
        with timeout_aware_processing(context, buffer_seconds=60) as monitor:
            for item in items:
                monitor.check_timeout(f"processing {item}")
                process(item)

    Args:
        context: Lambda context object
        buffer_seconds: Stop this many seconds before timeout

    Yields:
        LambdaTimeoutMonitor instance
    """
    monitor = LambdaTimeoutMonitor(context, buffer_seconds)
    try:
        yield monitor
    except TimeoutApproaching:
        logger.info(
            "Gracefully stopping due to timeout",
            extra=monitor.get_status()
        )
        raise


def get_timeout_buffer() -> int:
    """Get timeout buffer from environment or default."""
    return int(os.getenv('TIMEOUT_BUFFER_SECONDS', '60'))
