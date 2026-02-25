"""
Core holiday fetching logic.

Provides market holiday fetching from external APIs and detection
of holidays from price history gaps.

Supports both file-based storage (local) and DynamoDB storage (Lambda).
"""

import json
import os
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from logging_config import get_logger

logger = get_logger(__name__)


def is_lambda_environment() -> bool:
    """Check if running in AWS Lambda."""
    return bool(os.getenv('AWS_LAMBDA_FUNCTION_NAME'))


class HolidayFetcher:
    """
    Fetches and manages market holiday data.

    Can fetch holidays from:
    - Finnhub API (authoritative source)
    - Detection from price history gaps

    Storage:
    - Lambda: DynamoDB via ConfigService
    - Local: JSON file in config/market_holidays.json
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        use_dynamodb: Optional[bool] = None
    ):
        """
        Initialize the holiday fetcher.

        Args:
            config_path: Path to holidays JSON file. Defaults to config/market_holidays.json
            use_dynamodb: Use DynamoDB for storage. Defaults to True in Lambda, False locally.
        """
        if config_path:
            self.config_path = config_path
        else:
            # Default path relative to fetchers directory
            self.config_path = Path(__file__).parent.parent.parent / "config" / "market_holidays.json"

        # Auto-detect storage mode based on environment
        if use_dynamodb is None:
            self.use_dynamodb = is_lambda_environment()
        else:
            self.use_dynamodb = use_dynamodb

        self._config_service = None

    @property
    def config_service(self):
        """Lazy-load ConfigService for DynamoDB access."""
        if self._config_service is None:
            from config_service import get_config_service
            self._config_service = get_config_service()
        return self._config_service

    def fetch_from_finnhub(self, exchange: str = "US") -> Optional[Dict[str, Any]]:
        """
        Fetch market holidays from Finnhub API.

        Args:
            exchange: Exchange code (default: US)

        Returns:
            Dict with holiday data or None if unavailable
        """
        try:
            from fh_service import FinnhubService
            from api_keys import get_api_key

            api_key = get_api_key("FINNHUB_API_KEY")
            if not api_key:
                logger.warning("FINNHUB_API_KEY not configured, skipping API fetch")
                return None

            service = FinnhubService(api_key=api_key)
            return service.get_market_holidays(exchange)
        except Exception as e:
            logger.error("Error fetching holidays from Finnhub: %s", e)
            return None

    def detect_from_history(
        self,
        min_symbols_threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Detect holidays from price history gaps.

        Days missing from most symbols are likely market holidays.

        Args:
            min_symbols_threshold: Fraction of symbols that must be missing
                                   a day for it to be considered a holiday

        Returns:
            List of detected holiday dicts
        """
        try:
            from pricedata import list_symbols, get_price_history
        except ImportError:
            logger.warning("pricedata package not available, skipping detection")
            return []

        symbols = list_symbols()
        if not symbols:
            logger.warning("No symbols found in database")
            return []

        logger.info("Analyzing price history for %d symbols", len(symbols))

        # Get date range: last 60 days
        end_date = date.today()
        start_date = end_date - timedelta(days=60)

        # Collect all trading days per symbol
        all_dates_by_symbol: Dict[str, Set[date]] = {}
        all_dates: Set[date] = set()

        for symbol in symbols:
            history = get_price_history(symbol, start_date, end_date)
            if history:
                dates = set(history.keys())
                all_dates_by_symbol[symbol] = dates
                all_dates.update(dates)

        if not all_dates:
            logger.warning("No price history data found")
            return []

        # Generate all weekdays in the range
        weekdays: Set[date] = set()
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Not Saturday or Sunday
                weekdays.add(current)
            current += timedelta(days=1)

        # Find days that are weekdays but missing from most symbols
        symbols_with_data = [s for s in symbols if s in all_dates_by_symbol]
        if not symbols_with_data:
            return []

        detected_holidays: List[Dict[str, Any]] = []

        for day in sorted(weekdays):
            # Skip future dates and very recent dates
            if day >= date.today() - timedelta(days=1):
                continue

            # Count how many symbols are missing this day
            missing_count = sum(
                1 for s in symbols_with_data
                if day not in all_dates_by_symbol.get(s, set())
            )

            missing_fraction = missing_count / len(symbols_with_data)

            if missing_fraction >= min_symbols_threshold:
                detected_holidays.append({
                    "atDate": day.isoformat(),
                    "eventName": f"Detected holiday (missing from {missing_count}/{len(symbols_with_data)} symbols)",
                    "tradingHour": "",
                    "source": "detected"
                })

        return detected_holidays

    def load_existing(self, exchange: str = "US") -> Dict[str, Any]:
        """
        Load existing holidays from storage.

        Args:
            exchange: Exchange code to load holidays for

        Returns:
            Holiday data dict or empty dict if not found
        """
        # Try DynamoDB first if enabled
        if self.use_dynamodb:
            try:
                data = self.config_service.get_config("holidays", exchange)
                if data:
                    logger.debug("Loaded holidays from DynamoDB for exchange=%s", exchange)
                    return data
            except Exception as e:
                logger.warning("Could not load holidays from DynamoDB: %s", e)

        # Fall back to file
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Could not load existing holidays from file: %s", e)

        return {}

    def merge_holidays(
        self,
        api_holidays: Optional[Dict[str, Any]],
        detected_holidays: List[Dict[str, Any]],
        existing: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge holidays from different sources.

        API holidays take precedence over detected holidays.

        Args:
            api_holidays: Holidays from Finnhub API
            detected_holidays: Holidays detected from price gaps
            existing: Previously saved holidays

        Returns:
            Merged holiday data
        """
        result: Dict[str, Any] = {
            "exchange": api_holidays.get("exchange", "US") if api_holidays else "US",
            "timezone": api_holidays.get("timezone", "America/New_York") if api_holidays else "America/New_York",
            "last_updated": datetime.now().isoformat(),
            "holidays": []
        }

        api_dates: Set[str] = set()
        holidays_list: List[Dict[str, Any]] = []

        # Add API holidays first (authoritative)
        if api_holidays and api_holidays.get("data"):
            for holiday in api_holidays["data"]:
                date_str = holiday.get("atDate", "")
                if date_str:
                    api_dates.add(date_str)
                    holidays_list.append({
                        "atDate": date_str,
                        "eventName": holiday.get("eventName", "Unknown"),
                        "tradingHour": holiday.get("tradingHour", ""),
                        "source": "finnhub"
                    })

        # Add detected holidays that don't conflict
        for holiday in detected_holidays:
            date_str = holiday.get("atDate", "")
            if date_str and date_str not in api_dates:
                holidays_list.append(holiday)
                api_dates.add(date_str)

        # Preserve manually added holidays
        if existing.get("holidays"):
            for holiday in existing["holidays"]:
                date_str = holiday.get("atDate", "")
                source = holiday.get("source", "")
                if date_str and date_str not in api_dates and source == "manual":
                    holidays_list.append(holiday)
                    api_dates.add(date_str)

        # Sort by date
        holidays_list.sort(key=lambda x: x.get("atDate", ""))
        result["holidays"] = holidays_list

        return result

    def save(self, holidays: Dict[str, Any], exchange: str = "US") -> bool:
        """
        Save holidays to storage.

        In Lambda: saves to DynamoDB via ConfigService
        Locally: saves to JSON file

        Args:
            holidays: Holiday data to save
            exchange: Exchange code (used as config_key in DynamoDB)

        Returns:
            True if successful
        """
        # Save to DynamoDB if enabled
        if self.use_dynamodb:
            try:
                self.config_service.put_config("holidays", exchange, holidays)
                logger.info("Saved holidays to DynamoDB for exchange=%s", exchange)
                return True
            except Exception as e:
                logger.error("Error saving holidays to DynamoDB: %s", e)
                return False

        # Save to file (local mode)
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(holidays, f, indent=2)
            logger.info("Saved holidays to file: %s", self.config_path)
            return True
        except IOError as e:
            logger.error("Error saving holidays to file: %s", e)
            return False

    def fetch(
        self,
        exchange: str = "US",
        detect_missing: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch and update market holidays.

        This is the main entry point that:
        1. Loads existing holidays
        2. Fetches from Finnhub API
        3. Optionally detects missing days from price history
        4. Merges all sources
        5. Saves the result

        Args:
            exchange: Exchange code
            detect_missing: Whether to detect holidays from price gaps

        Returns:
            Dict with fetch results including counts and status
        """
        logger.info("Starting holiday fetch for exchange=%s, detect_missing=%s, use_dynamodb=%s",
                    exchange, detect_missing, self.use_dynamodb)

        # Load existing
        existing = self.load_existing(exchange)
        existing_count = len(existing.get("holidays", []))

        # Fetch from API
        api_holidays = self.fetch_from_finnhub(exchange)
        api_count = len(api_holidays.get("data", [])) if api_holidays else 0

        # Detect from history if requested
        detected_holidays: List[Dict[str, Any]] = []
        if detect_missing:
            detected_holidays = self.detect_from_history()
        detected_count = len(detected_holidays)

        # Merge
        merged = self.merge_holidays(api_holidays, detected_holidays, existing)
        total_count = len(merged.get("holidays", []))

        # Save
        saved = self.save(merged, exchange)

        # Count by source
        source_counts = Counter(
            h.get("source", "unknown") for h in merged.get("holidays", [])
        )

        result = {
            "success": saved,
            "exchange": exchange,
            "existing_count": existing_count,
            "api_count": api_count,
            "detected_count": detected_count,
            "total_count": total_count,
            "source_counts": dict(source_counts),
        }

        logger.info("Holiday fetch complete: %s", result)
        return result
