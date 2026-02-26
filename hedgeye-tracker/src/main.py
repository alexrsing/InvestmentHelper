import json
import os
import sys

from dotenv import load_dotenv

# Load environment variables from .env file before any other imports
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(env_path)

from handlers.database import Database
from handlers.gmail import Gmail
from services.trade_range_transformer import TradeRangeTransformer
from services.trend_range_transformer import TrendRangeTransformer
from util.logging_config import setup_logging, get_logger
from util.startup_validation import validate_startup

# Email subject names to search for
trade_range_gmail_name: str = "RISK RANGE™ SIGNALS:"
# Without trademark
# trade_range_gmail_name: str = "RISK RANGE SIGNALS:"
trend_range_gmail_name: str = "ETF Pro Plus - New Weekly Report"


def main():
    """
    Main function to retrieve all historic trend and trade range data from Gmail
    using a service account for authentication.
    """
    # Parse command line arguments for --skip-validation flag
    skip_validation = "--skip-validation" in sys.argv

    # Set up human-readable logging for CLI
    setup_logging()
    logger = get_logger(__name__)

    # Run startup validation before any processing
    validate_startup(skip_connectivity=skip_validation)

    print("=" * 80)
    print("FETCHING ALL HISTORIC TREND AND TRADE RANGE DATA FROM GMAIL")
    print("=" * 80)
    print()

    # Initialize Gmail handler (uses service account authentication)
    gmail = Gmail()

    # Fetch all Risk Range (Trade Range) emails
    print(f"Searching for: {trade_range_gmail_name}")
    print("-" * 80)
    risk_range_data = gmail.get_all_risk_range_emails()

    print()
    print(f"✓ Retrieved {len(risk_range_data)} risk range records")
    print()
    print("RISK RANGE DATA:")
    print(json.dumps(risk_range_data, indent=2, default=str))
    print()
    print("=" * 80)
    print()

    # Fetch all Trend Range emails
    print(f"Searching for: {trend_range_gmail_name}")
    print("-" * 80)
    trend_range_data = gmail.get_all_trend_range_emails()

    print()
    print(f"✓ Retrieved {len(trend_range_data)} trend range records")
    print()
    print("TREND RANGE DATA:")
    print(json.dumps(trend_range_data, indent=2, default=str))
    print()
    print("=" * 80)
    print()

    # Summary
    print("SUMMARY:")
    print(f"  Total Risk Range Records: {len(risk_range_data)}")
    print(f"  Total Trend Range Records: {len(trend_range_data)}")
    print(f"  Grand Total: {len(risk_range_data) + len(trend_range_data)}")
    print("=" * 80)
    print()

    # ========================================================================
    # TRANSFORM AND SAVE DATA TO DYNAMODB
    # ========================================================================
    print("=" * 80)
    print("TRANSFORMING AND SAVING DATA TO DYNAMODB")
    print("=" * 80)
    print()

    # Initialize transformers and database handler
    trade_transformer = TradeRangeTransformer()
    trend_transformer = TrendRangeTransformer()
    database = Database()

    # Transform risk range data to trade range format
    print("Transforming risk range data to trade range format...")
    trade_ranges = trade_transformer.transform_for_database(risk_range_data)
    print(f"✓ Transformed {len(trade_ranges)} unique tickers")
    print()

    # Transform trend range data to trend range format
    print("Transforming trend range data to trend range format...")
    trend_ranges = trend_transformer.transform_for_database(trend_range_data)
    print(f"✓ Transformed {len(trend_ranges)} unique tickers")
    print()

    # Save trade ranges to DynamoDB
    print("Saving trade ranges to etf_monitoring_trade_ranges table...")
    trade_count = database.batch_save_trade_ranges(trade_ranges)
    print(f"✓ Saved {trade_count} trade range records to DynamoDB")
    print()

    # Save trend ranges to DynamoDB
    print("Saving trend ranges to etf_monitoring_trend_ranges table...")
    trend_count = database.batch_save_trend_ranges(trend_ranges)
    print(f"✓ Saved {trend_count} trend range records to DynamoDB")
    print()

    # Final summary
    print("=" * 80)
    print("DATABASE SAVE SUMMARY:")
    print(f"  Trade Ranges Saved: {trade_count}")
    print(f"  Trend Ranges Saved: {trend_count}")
    print(f"  Total Records Saved: {trade_count + trend_count}")
    print("=" * 80)


if __name__ == "__main__":
    main()
