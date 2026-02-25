"""
HTML parser service for extracting risk ranges from Hedgeye HTML emails
"""

import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from services.symbol_mapping_service import SymbolMappingService

# import datetime
from util.logger import Logger

logger = Logger(__name__)


class RiskRangeParserService:
    """Service for parsing HTML emails and extracting risk range data"""

    # Color codes for trend detection
    TREND_COLORS = {
        "#00ae41": "BULLISH",  # Green
        "#eb0028": "BEARISH",  # Red
        "#999999": "NEUTRAL",  # Gray
        "#666666": "NEUTRAL",  # Dark gray (alternative)
    }

    def extract_risk_ranges_from_html(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Extract risk ranges from Hedgeye HTML email content

        Args:
            html_content: Raw HTML email content

        Returns:
            List of risk range dictionaries
        """
        try:
            if not html_content:
                logger.debug("No HTML content provided")
                return []

            soup = BeautifulSoup(html_content, "html.parser")
            risk_ranges = []

            # Find all tables in the email
            tables = soup.find_all("table")

            for table in tables:
                # Check if this table contains risk range data
                if self._is_risk_range_table(table):
                    ranges = self._extract_ranges_from_table(table)
                    risk_ranges.extend(ranges)

            logger.info(f"Extracted {len(risk_ranges)} risk ranges from HTML")
            return risk_ranges

        except Exception as e:
            logger.error(f"Error extracting risk ranges from HTML: {e}")
            return []

    def _is_risk_range_table(self, table) -> bool:
        """
        Check if a table contains risk range data

        Args:
            table: BeautifulSoup table element

        Returns:
            True if table contains risk range data
        """
        try:
            # Convert table to text and check for key indicators
            table_text = table.get_text().upper()

            # Check for headers that indicate risk range data from RISK RANGE™ SIGNALS emails
            has_buy_trade = "BUY TRADE" in table_text or "BUY" in table_text
            has_sell_trade = "SELL TRADE" in table_text or "SELL" in table_text
            has_prev_close = "PREV" in table_text and "CLOSE" in table_text

            # Also check for INDEX header which is common in risk range tables
            has_index = "INDEX" in table_text

            # Check for trend indicators (BULLISH, BEARISH, NEUTRAL)
            has_trend_indicators = any(trend in table_text for trend in ["BULLISH", "BEARISH", "NEUTRAL"])

            # Must have buy/sell trades or index, and preferably trend indicators
            return ((has_buy_trade and has_sell_trade) or has_index) and (has_trend_indicators or has_prev_close)

        except Exception:
            return False

    def _extract_ranges_from_table(self, table) -> List[Dict[str, Any]]:
        """
        Extract risk range data from a single table

        Args:
            table: BeautifulSoup table element

        Returns:
            List of risk range dictionaries
        """
        ranges = []

        try:
            rows = table.find_all("tr")

            # Find header row to determine column positions
            header_row = None
            header_index = -1

            for i, row in enumerate(rows):
                row_text = row.get_text().upper()
                if "BUY" in row_text or "SELL" in row_text or "INDEX" in row_text:
                    header_row = row
                    header_index = i
                    break

            if header_row is None:
                return ranges

            # Determine column indices
            headers = header_row.find_all(["th", "td"])
            col_indices = self._get_column_indices(headers)

            if not col_indices:
                return ranges

            # Process data rows (skip header row)
            for row in rows[header_index + 1 :]:
                cells = row.find_all(["td", "th"])

                if len(cells) < len(col_indices):
                    continue

                range_data = self._extract_range_from_row(cells, col_indices)
                if range_data:
                    ranges.append(range_data)

        except Exception as e:
            logger.error(f"Error extracting ranges from table: {e}")

        return ranges

    def _get_column_indices(self, headers) -> Dict[str, int]:
        """
        Determine column indices for data extraction

        Args:
            headers: List of header cells

        Returns:
            Dictionary mapping column names to indices
        """
        indices = {}

        for i, header in enumerate(headers):
            header_text = header.get_text().strip().upper()

            if "INDEX" in header_text or "SYMBOL" in header_text:
                indices["symbol"] = i
            elif "BUY" in header_text:
                indices["buy"] = i
            elif "SELL" in header_text:
                indices["sell"] = i
            elif "PREV" in header_text or "CLOSE" in header_text:
                indices["prev_close"] = i

        # Validate we have minimum required columns
        if "symbol" in indices and "buy" in indices and "sell" in indices:
            return indices

        # Alternative: Try to guess based on position if headers aren't clear
        if len(headers) >= 4:
            return {"symbol": 0, "buy": 1, "sell": 2, "prev_close": 3}

        return {}

    def _extract_range_from_row(self, cells, col_indices: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """
        Extract risk range data from a table row

        Args:
            cells: List of cell elements in the row
            col_indices: Dictionary mapping column names to indices

        Returns:
            Risk range dictionary or None if extraction fails
        """
        try:
            # Check if row has minimum required cells
            required_indices = ["symbol", "buy", "sell"]
            max_index = max(col_indices.get(col, -1) for col in required_indices if col in col_indices)
            if max_index >= len(cells):
                # Row doesn't have enough cells
                return None

            # Extract symbol and clean it
            symbol_cell = cells[col_indices["symbol"]]
            symbol_text = symbol_cell.get_text().strip()

            # Extract symbol and trend from formats like "SPX (BULLISH)" or "XLK (BEARISH)"
            # Also handle standalone symbols without trend indicators
            symbol_match = re.match(r"^([A-Z0-9/]+)(?:\s*\(([A-Z]+)\))?", symbol_text)
            if not symbol_match:
                # Try to extract just the symbol if no parentheses
                symbol_match = re.match(r"^([A-Z0-9/]+)", symbol_text)
                if not symbol_match:
                    return None

            original_symbol = symbol_match.group(1)
            trend_from_text = symbol_match.group(2) if symbol_match.lastindex and symbol_match.lastindex >= 2 else None

            # Apply symbol mapping
            symbol_mapping_service = SymbolMappingService()
            etf_symbol = symbol_mapping_service.map_symbol(original_symbol)

            # Extract trend from symbol text first, then fall back to cell styling
            if trend_from_text and trend_from_text in ["BULLISH", "BEARISH", "NEUTRAL"]:
                trend = trend_from_text
            else:
                trend = self._extract_trend(symbol_cell, symbol_text)

            # Extract buy trade value
            buy_cell = cells[col_indices["buy"]]
            buy_value = self._extract_numeric_value(buy_cell.get_text())

            # Extract sell trade value
            sell_cell = cells[col_indices["sell"]]
            sell_value = self._extract_numeric_value(sell_cell.get_text())

            # Extract previous close if available
            prev_close = None
            if "prev_close" in col_indices and col_indices["prev_close"] < len(cells):
                prev_cell = cells[col_indices["prev_close"]]
                prev_close = self._extract_numeric_value(prev_cell.get_text())

            # Validate extracted data
            if not etf_symbol or buy_value is None or sell_value is None:
                logger.debug(f"Invalid data: symbol={etf_symbol}, buy={buy_value}, sell={sell_value}")
                return None

            return {
                "original_symbol": original_symbol,  # Original symbol before mapping
                "etf_symbol": etf_symbol,  # Mapped symbol
                "buy_trade": str(buy_value),  # Convert to string for DynamoDB
                "sell_trade": str(sell_value),  # Convert to string for DynamoDB
                "prev_close": str(prev_close) if prev_close is not None else None,  # Convert to string for DynamoDB
                "trend": trend,
                "source": "gmail_hedgeye_risk_range",
            }

        except Exception as e:
            logger.debug(f"Error extracting range from row: {e}")
            return None

    def _extract_trend(self, cell, text: str) -> str:
        """
        Extract trend indicator from cell styling or text

        Args:
            cell: BeautifulSoup cell element
            text: Cell text content

        Returns:
            Trend indicator (BULLISH, BEARISH, or NEUTRAL)
        """
        # Check text for trend keywords
        text_upper = text.upper()
        if "BULLISH" in text_upper:
            return "BULLISH"
        elif "BEARISH" in text_upper:
            return "BEARISH"
        elif "NEUTRAL" in text_upper:
            return "NEUTRAL"

        # Check cell color styling
        style = cell.get("style", "")
        for color, trend in self.TREND_COLORS.items():
            if color in style:
                return trend

        # Check nested elements for color
        for elem in cell.find_all(["span", "font", "strong", "em"]):
            elem_style = elem.get("style", "")
            for color, trend in self.TREND_COLORS.items():
                if color in elem_style:
                    return trend

        # Default to NEUTRAL if no trend indicator found
        return "NEUTRAL"

    def _extract_numeric_value(self, text: str) -> Optional[float]:
        """
        Extract numeric value from text

        Args:
            text: Text containing numeric value

        Returns:
            Float value or None if extraction fails
        """
        try:
            if not text:
                return None

            # Remove common formatting characters like commas, dollar signs, spaces
            cleaned = text.strip().replace(",", "").replace("$", "").replace(" ", "")

            # Remove any remaining non-numeric characters except decimal point and negative sign
            cleaned = re.sub(r"[^\d\.\-]", "", cleaned)

            if cleaned and cleaned != "-" and cleaned != ".":
                return float(cleaned)

            return None

        except (ValueError, AttributeError):
            return None

    def validate_extracted_data(self, risk_ranges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate and clean extracted risk range data

        Args:
            risk_ranges: List of extracted risk ranges

        Returns:
            List of validated risk ranges
        """
        validated = []

        # Tickers to exclude (Treasury yield indicators)
        excluded_tickers = {"UST30Y", "UST10Y", "UST2Y"}

        for range_data in risk_ranges:
            try:
                # Ensure required fields are present
                if not all(key in range_data for key in ["etf_symbol", "buy_trade", "sell_trade"]):
                    continue

                # Filter out excluded tickers
                if range_data["etf_symbol"] in excluded_tickers:
                    logger.debug(f"Filtering out excluded ticker: {range_data['etf_symbol']}")
                    continue

                # Validate ETF symbol format (allow various lengths and formats)
                if not re.match(r"^[A-Z0-9]{1,10}$", range_data["etf_symbol"]):
                    continue

                # Validate numeric values (convert strings back to float for comparison)
                try:
                    buy_val = float(range_data["buy_trade"])
                    sell_val = float(range_data["sell_trade"])
                    if buy_val <= 0 or sell_val <= 0:
                        continue

                    # Ensure buy is less than sell (typical for risk ranges)
                    if buy_val >= sell_val:
                        logger.warning(f"Buy >= Sell for {range_data['etf_symbol']}: {buy_val} >= {sell_val}")
                except (ValueError, TypeError):
                    continue

                validated.append(range_data)

            except Exception as e:
                logger.debug(f"Validation error for range data: {e}")
                continue

        return validated
