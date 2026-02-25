#!/usr/bin/env python3
"""
CLI tool to fetch and manage market holidays.

Usage:
    python scripts/fetch_holidays.py [--detect-missing] [--exchange US]

Options:
    --detect-missing, -d   Also detect missing days from price history data
    --exchange, -e         Exchange code (default: US)
    --output, -o           Output file path (default: config/market_holidays.json)
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

# Add fetchers and src directories to path
fetchers_dir = Path(__file__).parent.parent / "fetchers"
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(fetchers_dir))
sys.path.insert(0, str(src_dir))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

from logging_config import setup_logging, get_logger
from core.holiday_fetcher import HolidayFetcher

logger = get_logger(__name__)


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Fetch and manage market holidays"
    )
    parser.add_argument(
        "--detect-missing", "-d",
        action="store_true",
        help="Also detect missing days from price history data"
    )
    parser.add_argument(
        "--exchange", "-e",
        default="US",
        help="Exchange code (default: US)"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (default: config/market_holidays.json)"
    )
    args = parser.parse_args()

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(__file__).parent.parent / "config" / "market_holidays.json"

    logger.info("Market Holiday Manager")
    logger.info("=" * 50)
    logger.info("Exchange: %s", args.exchange)
    logger.info("Output: %s", output_path)
    logger.info("")

    # Initialize fetcher with custom output path
    fetcher = HolidayFetcher(config_path=output_path)

    # Load existing holidays
    existing = fetcher.load_existing()
    if existing.get("holidays"):
        logger.info("Loaded %d existing holidays", len(existing['holidays']))

    # Fetch from Finnhub API
    logger.info("Fetching holidays from Finnhub API...")
    api_holidays = fetcher.fetch_from_finnhub(args.exchange)
    if api_holidays and api_holidays.get("data"):
        logger.info("  Found %d holidays from API", len(api_holidays['data']))
    else:
        logger.info("  No holidays returned from API")

    # Detect missing days if requested
    detected_holidays = []
    if args.detect_missing:
        logger.info("Detecting missing days from price history...")
        detected_holidays = fetcher.detect_from_history()
        if detected_holidays:
            logger.info("  Detected %d potential holidays", len(detected_holidays))
        else:
            logger.info("  No additional holidays detected")

    # Merge all sources
    merged = fetcher.merge_holidays(api_holidays, detected_holidays, existing)

    # Save to file
    logger.info("Saving %d holidays to %s...", len(merged['holidays']), output_path)
    if fetcher.save(merged):
        logger.info("Success!")
    else:
        logger.error("Failed to save holidays")
        return 1

    # Print summary
    logger.info("=" * 50)
    logger.info("Holiday Summary:")

    source_counts = Counter(h.get("source", "unknown") for h in merged["holidays"])
    for source, count in sorted(source_counts.items()):
        logger.info("  %s: %d", source, count)

    # Show upcoming holidays
    from datetime import date
    today = date.today()
    upcoming = [
        h for h in merged["holidays"]
        if h.get("atDate", "") >= today.isoformat()
    ][:5]

    if upcoming:
        logger.info("Upcoming holidays:")
        for h in upcoming:
            name = h.get("eventName", "Unknown")
            date_str = h.get("atDate", "")
            hours = h.get("tradingHour", "")
            status = f" (early close: {hours})" if hours else ""
            logger.info("  %s: %s%s", date_str, name, status)

    return 0


if __name__ == "__main__":
    sys.exit(main())
