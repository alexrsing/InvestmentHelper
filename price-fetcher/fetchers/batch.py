"""
Batch processing utilities for Lambda execution.

Provides symbol batching and limiting to prevent Lambda timeout
when processing large symbol lists.
"""

import os
from typing import List, Optional

from logging_config import get_logger

logger = get_logger(__name__)


def get_batch_config() -> dict:
    """
    Get batch processing configuration from environment.

    Returns:
        Dict with batch configuration:
        - max_symbols_per_run: Maximum symbols to process in one invocation
        - batch_size: Size of internal processing batches
    """
    return {
        'max_symbols_per_run': int(os.getenv('MAX_SYMBOLS_PER_RUN', '50')),
        'batch_size': int(os.getenv('BATCH_SIZE', '10')),
    }


def split_into_batches(symbols: List[str], batch_size: int) -> List[List[str]]:
    """
    Split symbol list into batches for processing.

    Args:
        symbols: List of symbols to process
        batch_size: Maximum symbols per batch

    Returns:
        List of symbol batches
    """
    if batch_size <= 0:
        return [symbols] if symbols else []

    batches = []
    for i in range(0, len(symbols), batch_size):
        batches.append(symbols[i:i + batch_size])

    return batches


def get_symbols_for_run(
    all_symbols: List[str],
    max_symbols: Optional[int] = None,
    offset: int = 0
) -> List[str]:
    """
    Get symbols for this Lambda run, respecting limits.

    Args:
        all_symbols: Complete list of symbols
        max_symbols: Override max symbols (from event), uses env config if None
        offset: Starting offset for pagination

    Returns:
        Subset of symbols to process in this run
    """
    config = get_batch_config()
    limit = max_symbols if max_symbols is not None else config['max_symbols_per_run']

    # Apply offset first
    if offset > 0:
        if offset >= len(all_symbols):
            logger.info(
                "Offset exceeds symbol count, nothing to process",
                extra={'offset': offset, 'total_symbols': len(all_symbols)}
            )
            return []
        all_symbols = all_symbols[offset:]

    # Apply limit
    if limit and len(all_symbols) > limit:
        logger.info(
            "Limiting symbols for this run",
            extra={
                'limit': limit,
                'total_available': len(all_symbols),
                'offset': offset
            }
        )
        return all_symbols[:limit]

    return all_symbols


def calculate_remaining_symbols(
    total_symbols: int,
    processed_count: int,
    offset: int = 0
) -> dict:
    """
    Calculate remaining work after a run.

    Args:
        total_symbols: Total number of symbols
        processed_count: Number processed in this run
        offset: Starting offset for this run

    Returns:
        Dict with pagination info for next run
    """
    next_offset = offset + processed_count
    remaining = total_symbols - next_offset

    return {
        'total_symbols': total_symbols,
        'processed_this_run': processed_count,
        'next_offset': next_offset if remaining > 0 else None,
        'remaining_symbols': max(0, remaining),
        'is_complete': remaining <= 0
    }
