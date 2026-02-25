import argparse
import datetime as dt
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from db_service import DBService
from yf_service import YahooFinanceService, YFINANCE_AVAILABLE
from av_service import AlphaVantageService
from td_service import TwelveDataService
from fh_service import FinnhubService
from fmp_service import FMPService
from logging_config import setup_logging, get_logger
from api_keys import get_api_key
from timeout import TimeoutApproaching, timeout_aware_processing, get_timeout_buffer

logger = get_logger(__name__)


def _load_local_config():
    """Load .env file for local development only."""
    if os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
        return  # Skip in Lambda - use Secrets Manager instead

    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass  # python-dotenv not installed


# Load local config on module import (for CLI usage)
_load_local_config()


class PriceDataFetcher:
    """
    Fetches price data using configurable sources.

    DATA_SOURCE options:
    - 'auto': Try yfinance first, fall back to paid APIs (default)
    - 'yfinance': Only use Yahoo Finance
    - 'alphavantage': Only use Alpha Vantage
    - 'twelvedata': Only use Twelve Data
    - 'finnhub': Only use Finnhub
    - 'fmp': Only use Financial Modeling Prep
    """

    VALID_SOURCES = {'auto', 'yfinance', 'alphavantage', 'twelvedata', 'finnhub', 'fmp'}

    def __init__(self, data_source: Optional[str] = None):
        # Determine data source from parameter or environment
        self.data_source = (data_source or os.getenv("DATA_SOURCE", "auto")).lower()
        if self.data_source not in self.VALID_SOURCES:
            logger.warning("Invalid DATA_SOURCE '%s', using 'auto'", self.data_source)
            self.data_source = "auto"

        logger.info("Data source mode: %s", self.data_source)

        # Initialize yfinance if needed and available
        self.yf_service: Optional[YahooFinanceService] = None
        if self.data_source in ("auto", "yfinance"):
            if YFINANCE_AVAILABLE:
                self.yf_service = YahooFinanceService()
                logger.info("Yahoo Finance initialized")
            elif self.data_source == "yfinance":
                raise ImportError("DATA_SOURCE=yfinance requires yfinance package. Install with: pip install yfinance")
            else:
                logger.info("yfinance not available, skipping Yahoo Finance in auto mode")

        # Initialize Alpha Vantage if needed
        self.av_service: Optional[AlphaVantageService] = None
        if self.data_source in ("auto", "alphavantage"):
            av_api_key = get_api_key("ALPHA_VANTAGE_API_KEY")
            if av_api_key:
                av_tier = get_api_key("ALPHA_VANTAGE_TIER") or "free"
                try:
                    self.av_service = AlphaVantageService(api_key=av_api_key, tier=av_tier)
                    logger.info("Alpha Vantage initialized (tier: %s)", av_tier)
                except Exception as e:
                    logger.warning("Could not initialize Alpha Vantage: %s", e)
            elif self.data_source == "alphavantage":
                raise ValueError("DATA_SOURCE=alphavantage requires ALPHA_VANTAGE_API_KEY")
            else:
                logger.debug("Alpha Vantage not configured (no API key)")

        # Initialize Twelve Data if needed
        self.td_service: Optional[TwelveDataService] = None
        if self.data_source in ("auto", "twelvedata"):
            td_api_key = get_api_key("TWELVEDATA_API_KEY")
            if td_api_key:
                td_tier = get_api_key("TWELVEDATA_TIER") or "free"
                try:
                    self.td_service = TwelveDataService(api_key=td_api_key, tier=td_tier)
                    logger.info("Twelve Data initialized (tier: %s)", td_tier)
                except Exception as e:
                    logger.warning("Could not initialize Twelve Data: %s", e)
            elif self.data_source == "twelvedata":
                raise ValueError("DATA_SOURCE=twelvedata requires TWELVEDATA_API_KEY")
            else:
                logger.debug("Twelve Data not configured (no API key)")

        # Initialize Finnhub if needed
        self.fh_service: Optional[FinnhubService] = None
        if self.data_source in ("auto", "finnhub"):
            fh_api_key = get_api_key("FINNHUB_API_KEY")
            if fh_api_key:
                fh_tier = get_api_key("FINNHUB_TIER") or "free"
                try:
                    self.fh_service = FinnhubService(api_key=fh_api_key, tier=fh_tier)
                    logger.info("Finnhub initialized (tier: %s)", fh_tier)
                except Exception as e:
                    logger.warning("Could not initialize Finnhub: %s", e)
            elif self.data_source == "finnhub":
                raise ValueError("DATA_SOURCE=finnhub requires FINNHUB_API_KEY")
            else:
                logger.debug("Finnhub not configured (no API key)")

        # Initialize Financial Modeling Prep if needed
        self.fmp_service: Optional[FMPService] = None
        if self.data_source in ("auto", "fmp"):
            fmp_api_key = get_api_key("FMP_API_KEY")
            if fmp_api_key:
                fmp_tier = get_api_key("FMP_TIER") or "free"
                try:
                    self.fmp_service = FMPService(api_key=fmp_api_key, tier=fmp_tier)
                    logger.info("Financial Modeling Prep initialized (tier: %s)", fmp_tier)
                except Exception as e:
                    logger.warning("Could not initialize FMP: %s", e)
            elif self.data_source == "fmp":
                raise ValueError("DATA_SOURCE=fmp requires FMP_API_KEY")
            else:
                logger.debug("Financial Modeling Prep not configured (no API key)")

    def _is_valid_price_info(self, data: Optional[Dict[str, Any]]) -> bool:
        """Check if price info contains valid data."""
        if not data:
            return False
        # Must have at least a price to be considered valid
        price = data.get('regularMarketPrice')
        return price is not None and price > 0

    def get_info(self, symbol: str) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Get current quote info for a symbol.
        Returns (data, source) tuple.
        """
        # Try Yahoo Finance if enabled
        if self.yf_service:
            try:
                data = self.yf_service.get_info(symbol)
                if self._is_valid_price_info(data):
                    return data, "yfinance"
                elif self.data_source == "yfinance":
                    logger.warning("yfinance returned invalid/empty data", extra={'symbol': symbol})
            except Exception as e:
                if self.data_source == "yfinance":
                    logger.warning("yfinance failed: %s", e, extra={'symbol': symbol})

        # Try Twelve Data if enabled
        if self.td_service:
            try:
                data = self.td_service.get_info(symbol)
                if self._is_valid_price_info(data):
                    return data, "twelvedata"
                elif self.data_source == "twelvedata":
                    logger.warning("twelvedata returned invalid/empty data", extra={'symbol': symbol})
            except Exception as e:
                logger.warning("twelvedata failed: %s", e, extra={'symbol': symbol})

        # Try Alpha Vantage if enabled
        if self.av_service:
            try:
                data = self.av_service.get_info(symbol)
                if self._is_valid_price_info(data):
                    return data, "alphavantage"
                elif self.data_source == "alphavantage":
                    logger.warning("alphavantage returned invalid/empty data", extra={'symbol': symbol})
            except Exception as e:
                logger.warning("alphavantage failed: %s", e, extra={'symbol': symbol})

        # Try Finnhub if enabled
        if self.fh_service:
            try:
                data = self.fh_service.get_info(symbol)
                if self._is_valid_price_info(data):
                    return data, "finnhub"
                elif self.data_source == "finnhub":
                    logger.warning("finnhub returned invalid/empty data", extra={'symbol': symbol})
            except Exception as e:
                logger.warning("finnhub failed: %s", e, extra={'symbol': symbol})

        # Try Financial Modeling Prep if enabled
        if self.fmp_service:
            try:
                data = self.fmp_service.get_info(symbol)
                if self._is_valid_price_info(data):
                    return data, "fmp"
                elif self.data_source == "fmp":
                    logger.warning("fmp returned invalid/empty data", extra={'symbol': symbol})
            except Exception as e:
                logger.warning("fmp failed: %s", e, extra={'symbol': symbol})

        return None, "none"

    def get_historical_data(
        self,
        symbol: str,
        period: str,
        interval: str
    ) -> Tuple[Optional[List[Dict[str, Any]]], str]:
        """
        Get historical price data for a symbol.
        Returns (data, source) tuple.
        """
        # Try Yahoo Finance if enabled
        if self.yf_service:
            try:
                data = self.yf_service.get_historical_data(symbol, period, interval)
                if data and len(data) > 0:
                    return data, "yfinance"
            except Exception as e:
                if self.data_source == "yfinance":
                    logger.warning("yfinance history failed: %s", e, extra={'symbol': symbol, 'interval': interval})

        # Try Twelve Data if enabled
        if self.td_service:
            try:
                data = self.td_service.get_historical_data(symbol, period, interval)
                if data and len(data) > 0:
                    return data, "twelvedata"
            except Exception as e:
                if self.data_source == "twelvedata":
                    logger.warning("twelvedata history failed: %s", e, extra={'symbol': symbol, 'interval': interval})

        # Try Alpha Vantage if enabled
        if self.av_service:
            try:
                data = self.av_service.get_historical_data(symbol, period, interval)
                if data and len(data) > 0:
                    return data, "alphavantage"
            except Exception as e:
                logger.warning("alphavantage history failed: %s", e, extra={'symbol': symbol, 'interval': interval})

        # Try Finnhub if enabled
        if self.fh_service:
            try:
                data = self.fh_service.get_historical_data(symbol, period, interval)
                if data and len(data) > 0:
                    return data, "finnhub"
            except Exception as e:
                logger.warning("finnhub history failed: %s", e, extra={'symbol': symbol, 'interval': interval})

        # Try Financial Modeling Prep if enabled
        if self.fmp_service:
            try:
                data = self.fmp_service.get_historical_data(symbol, period, interval)
                if data and len(data) > 0:
                    return data, "fmp"
            except Exception as e:
                logger.warning("fmp history failed: %s", e, extra={'symbol': symbol, 'interval': interval})

        return None, "none"

    def get_api_status(self) -> Dict[str, Any]:
        """Get rate limit status for all configured APIs."""
        status = {}
        if self.av_service:
            status["alphavantage"] = self.av_service.get_remaining_requests()
        if self.td_service:
            status["twelvedata"] = self.td_service.get_remaining_credits()
        if self.fh_service:
            status["finnhub"] = self.fh_service.get_remaining_calls()
        if self.fmp_service:
            status["fmp"] = self.fmp_service.get_remaining_requests()
        return status

    def fetch_prices(
        self,
        symbols: List[str],
        context: Optional[Any] = None,
        db_service: Optional[DBService] = None
    ) -> Dict[str, Any]:
        """
        Fetch prices for a list of symbols with timeout awareness.

        This method is designed for Lambda execution with graceful timeout handling.
        Processing stops before timeout to allow returning partial results.

        Args:
            symbols: List of symbols to fetch
            context: Lambda context object (for timeout monitoring)
            db_service: Optional DBService for storing results

        Returns:
            Dict with:
            - success: List of successfully fetched symbols
            - failed: List of failed symbols
            - skipped: List of skipped symbols (no data available)
            - timeout_remaining: Symbols not processed due to timeout
            - data: Dict of fetched ticker data
            - timeout_triggered: Whether timeout caused early exit
        """
        buffer_seconds = get_timeout_buffer()

        results: Dict[str, Any] = {
            'success': [],
            'failed': [],
            'skipped': [],
            'timeout_remaining': [],
            'data': {},
            'timeout_triggered': False,
            'sources_used': {}
        }

        current_timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
        current_date = dt.datetime.now(dt.timezone.utc).date().isoformat()

        try:
            with timeout_aware_processing(context, buffer_seconds) as monitor:
                for i, symbol in enumerate(symbols):
                    # Check timeout before processing each symbol
                    try:
                        monitor.check_timeout(f"fetch {symbol}")
                    except TimeoutApproaching:
                        # Record remaining symbols and exit
                        results['timeout_remaining'] = symbols[i:]
                        results['timeout_triggered'] = True
                        raise

                    try:
                        # Fetch price info
                        price_info, source = self.get_info(symbol)

                        if price_info is None:
                            logger.warning(
                                "No data returned",
                                extra={'symbol': symbol}
                            )
                            results['skipped'].append(symbol)
                            continue

                        # Track source usage
                        results['sources_used'][source] = results['sources_used'].get(source, 0) + 1

                        # Fetch daily historical data (OHLCV)
                        history_1d, _ = self.get_historical_data(symbol, period='1mo', interval='1d')

                        results['data'][symbol] = {
                            'price_info': price_info,
                            'history_1d': history_1d,
                            'source': source,
                        }
                        results['success'].append(symbol)

                        logger.info(
                            "Success via %s",
                            source,
                            extra={'symbol': symbol, 'progress': f"{i+1}/{len(symbols)}"}
                        )

                    except TimeoutApproaching:
                        raise
                    except Exception as e:
                        logger.error(
                            "Failed: %s",
                            type(e).__name__,
                            extra={'symbol': symbol, 'error': str(e)}
                        )
                        results['failed'].append(symbol)

        except TimeoutApproaching:
            logger.info(
                "Processing stopped due to timeout",
                extra={
                    'processed': len(results['success']) + len(results['failed']) + len(results['skipped']),
                    'remaining': len(results['timeout_remaining'])
                }
            )

        # Store results in DB if service provided
        if db_service and results['data']:
            try:
                for symbol, data in results['data'].items():
                    db_service.save_etf(symbol, data['price_info'], data['source'])
                    if data.get('history_1d'):
                        db_service.save_etf_history(symbol, data['history_1d'])
                logger.info(
                    "Stored results in DynamoDB",
                    extra={'count': len(results['data'])}
                )
            except Exception as e:
                logger.error(
                    "DB storage failed",
                    extra={'error': type(e).__name__, 'message': str(e)}
                )

        return results


def get_staleness_minutes(last_fetched_at: Optional[str]) -> Optional[float]:
    """Calculate how many minutes since the last fetch.

    Args:
        last_fetched_at: ISO 8601 timestamp of last fetch, or None

    Returns:
        Minutes since last fetch, or None if no valid timestamp
    """
    if not last_fetched_at:
        return None

    try:
        last_fetch = dt.datetime.fromisoformat(last_fetched_at.replace('Z', '+00:00'))
        if last_fetch.tzinfo:
            now = dt.datetime.now(dt.timezone.utc)
        else:
            now = dt.datetime.now()
        return (now - last_fetch).total_seconds() / 60
    except (ValueError, TypeError):
        return None


def format_staleness(minutes: Optional[float]) -> str:
    """Format staleness duration for display.

    Args:
        minutes: Staleness in minutes, or None if unknown

    Returns:
        Human-readable staleness string (e.g., "2h 15m", "new")
    """
    if minutes is None:
        return "new"

    if minutes < 60:
        return f"{int(minutes)}m"
    elif minutes < 1440:  # Less than 24 hours
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        return f"{hours}h {mins}m" if mins else f"{hours}h"
    else:
        days = int(minutes // 1440)
        hours = int((minutes % 1440) // 60)
        return f"{days}d {hours}h" if hours else f"{days}d"


def is_symbol_fresh(
    last_fetched_at: Optional[str],
    threshold_minutes: int
) -> bool:
    """Check if a symbol's data is fresh (within staleness threshold).

    Args:
        last_fetched_at: ISO 8601 timestamp of last fetch, or None
        threshold_minutes: Minutes within which data is considered fresh

    Returns:
        True if data is fresh and should be skipped, False if stale/missing
    """
    age_minutes = get_staleness_minutes(last_fetched_at)
    if age_minutes is None:
        return False  # No data = stale
    return age_minutes < threshold_minutes


def main():
    # Setup logging first
    setup_logging()

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Fetch ETF price data")
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force refresh all symbols, ignoring staleness threshold"
    )
    args = parser.parse_args()

    # Get current datetime
    now = dt.datetime.now(dt.timezone.utc)
    current_date: str = now.date().isoformat()
    current_timestamp: str = now.isoformat()

    # Get staleness threshold from environment (default: 15 minutes)
    staleness_threshold = int(os.getenv("STALENESS_THRESHOLD_MINUTES", "15"))

    # Get max symbols per run (None = unlimited)
    max_symbols_env = os.getenv("MAX_SYMBOLS_PER_RUN", "").strip()
    max_symbols_per_run: Optional[int] = int(max_symbols_env) if max_symbols_env else None

    # Check for force refresh (command line or environment)
    force_refresh_env = os.getenv("FORCE_REFRESH", "false").lower() in ("true", "1", "yes")
    force_refresh = args.force or force_refresh_env

    # Initialize services
    db_service = DBService()
    fetcher = PriceDataFetcher()

    # Pull enabled symbols from watchlist table
    etf_symbols = db_service.get_watchlist_symbols(enabled_only=True)
    etf_symbols = list(set(etf_symbols))  # Dedupe just in case
    # Note: get_watchlist_symbols already sorts by priority

    logger.info("ETF symbols found: %d", len(etf_symbols))

    if force_refresh:
        logger.info("Force refresh enabled - ignoring staleness threshold")
    else:
        logger.info("Staleness threshold: %d minutes", staleness_threshold)

    # Query existing timestamps and filter out fresh symbols
    price_timestamps = db_service.get_price_timestamps(etf_symbols)
    symbols_with_staleness: List[Tuple[str, Optional[float]]] = []
    skipped_symbols: List[str] = []

    for symbol in etf_symbols:
        last_fetched = price_timestamps.get(symbol)
        staleness = get_staleness_minutes(last_fetched)

        # Skip fresh symbols unless force refresh is enabled
        if not force_refresh and is_symbol_fresh(last_fetched, staleness_threshold):
            skipped_symbols.append(symbol)
        else:
            symbols_with_staleness.append((symbol, staleness))

    # Sort by staleness: None (new symbols) first, then oldest to newest
    # None values get sorted first by using infinity as fallback
    symbols_with_staleness.sort(key=lambda x: (x[1] is not None, -(x[1] or 0)))

    if skipped_symbols:
        logger.info("Skipping %d symbols with fresh data", len(skipped_symbols))

    # Apply max symbols limit if configured
    total_stale = len(symbols_with_staleness)
    limited_by_max = False
    if max_symbols_per_run and len(symbols_with_staleness) > max_symbols_per_run:
        symbols_with_staleness = symbols_with_staleness[:max_symbols_per_run]
        limited_by_max = True

    if limited_by_max:
        logger.info(
            "Symbols to fetch: %d/%d (limited by MAX_SYMBOLS_PER_RUN=%d)",
            len(symbols_with_staleness), total_stale, max_symbols_per_run
        )
    else:
        logger.info("Symbols to fetch: %d", len(symbols_with_staleness))

    # For each etf_symbol, get info and daily price history (OHLCV)
    successful_tickers: List[str] = []
    failed_tickers: List[str] = []
    sources_used: Dict[str, int] = {"yfinance": 0, "alphavantage": 0, "twelvedata": 0, "finnhub": 0, "fmp": 0}

    for i, (ticker, staleness) in enumerate(symbols_with_staleness, 1):
        staleness_str = format_staleness(staleness)
        logger.info(
            "[%d/%d] Processing %s (stale: %s)",
            i, len(symbols_with_staleness), ticker, staleness_str
        )
        try:
            price_info, source = fetcher.get_info(ticker)

            # Handle case where no data source returned data
            if price_info is None:
                logger.warning("No info returned, skipping", extra={'symbol': ticker})
                failed_tickers.append(ticker)
                continue

            sources_used[source] = sources_used.get(source, 0) + 1

            # Fetch daily historical data (OHLCV)
            history_1d, _ = fetcher.get_historical_data(ticker, period='1mo', interval='1d')

            # Save ETF record via PynamoDB
            db_service.save_etf(ticker, price_info, source)

            # Save history records via PynamoDB
            if history_1d:
                db_service.save_etf_history(ticker, history_1d)

            successful_tickers.append(ticker)
            logger.info("Success via %s", source, extra={'symbol': ticker})

        except Exception as e:
            logger.error("Failed: %s: %s", type(e).__name__, e, extra={'symbol': ticker})
            failed_tickers.append(ticker)
            continue

    # Summary
    sources_str = ", ".join(f"{k}={v}" for k, v in sources_used.items() if v > 0)
    logger.info(
        "Fetch complete: total=%d, skipped=%d, fetched=%d, failed=%d, sources=%s",
        len(etf_symbols),
        len(skipped_symbols),
        len(successful_tickers),
        len(failed_tickers),
        sources_str or 'none'
    )
    if failed_tickers:
        logger.warning("Failed symbols: %s", ', '.join(failed_tickers))

    # Show API rate limit status
    api_status = fetcher.get_api_status()
    for api_name, status in api_status.items():
        remaining = status.get('remaining_today', 'N/A')
        logger.info("%s: %s requests remaining today", api_name, remaining)


if __name__ == "__main__":
    main()
