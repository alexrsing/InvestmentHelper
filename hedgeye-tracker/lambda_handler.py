"""
AWS Lambda Handler for Hedgeye Risk Ranges Tracker

Wraps the main application logic for Lambda execution.
"""

import json
import os
import sys

# Ensure the src directory is in the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from util.logging_config import setup_logging, get_logger

setup_logging()

from handlers.database import Database
from handlers.gmail import Gmail
from services.trade_range_transformer import TradeRangeTransformer
from services.trend_range_transformer import TrendRangeTransformer

# Email subject names to search for
TRADE_RANGE_GMAIL_NAME = "RISK RANGE™ SIGNALS:"
TREND_RANGE_GMAIL_NAME = "ETF Pro Plus - New Weekly Report"


def handler(event, context):
    """
    Lambda handler function.

    Args:
        event: Lambda event (can contain optional parameters)
        context: Lambda context

    Returns:
        dict: Response with status and summary
    """
    logger = get_logger("lambda_handler")

    try:
        logger.info("Starting Hedgeye Risk Ranges Tracker Lambda execution")
        logger.info(f"Event: {json.dumps(event)}")

        # Initialize components
        gmail = Gmail()
        trade_transformer = TradeRangeTransformer()
        trend_transformer = TrendRangeTransformer()
        database = Database()

        # Fetch risk range emails
        logger.info(f"Searching for: {TRADE_RANGE_GMAIL_NAME}")
        risk_range_data = gmail.get_all_risk_range_emails()
        logger.info(f"Retrieved {len(risk_range_data)} risk range records")

        # Fetch trend range emails
        logger.info(f"Searching for: {TREND_RANGE_GMAIL_NAME}")
        trend_range_data = gmail.get_all_trend_range_emails()
        logger.info(f"Retrieved {len(trend_range_data)} trend range records")

        # Transform data
        logger.info("Transforming risk range data...")
        trade_ranges = trade_transformer.transform_for_database(risk_range_data)
        logger.info(f"Transformed {len(trade_ranges)} unique trade range tickers")

        logger.info("Transforming trend range data...")
        trend_ranges = trend_transformer.transform_for_database(trend_range_data)
        logger.info(f"Transformed {len(trend_ranges)} unique trend range tickers")

        # Save to DynamoDB
        logger.info("Saving trade ranges to DynamoDB...")
        trade_count = database.batch_save_trade_ranges(trade_ranges)
        logger.info(f"Saved {trade_count} trade range records")

        logger.info("Saving trend ranges to DynamoDB...")
        trend_count = database.batch_save_trend_ranges(trend_ranges)
        logger.info(f"Saved {trend_count} trend range records")

        # Build response
        summary = {
            "risk_range_emails": len(risk_range_data),
            "trend_range_emails": len(trend_range_data),
            "trade_ranges_saved": trade_count,
            "trend_ranges_saved": trend_count,
            "total_saved": trade_count + trend_count
        }

        logger.info(f"Execution complete: {json.dumps(summary)}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Hedgeye Risk Ranges Tracker completed successfully",
                "summary": summary
            })
        }

    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Hedgeye Risk Ranges Tracker failed",
                "error": str(e)
            })
        }
