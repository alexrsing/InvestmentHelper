"""
HTML parser service for extracting trend ranges from ETF Pro Plus emails
"""

import datetime
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from services.symbol_mapping_service import SymbolMappingService
from util.logging_config import get_logger

logger = get_logger(__name__)


class TrendRangeParserService:
    """Service for parsing ETF Pro Plus trend range data from HTML emails"""

    # Color codes for trend detection
    BULLISH_COLOR = "#00ae41"  # Green
    BEARISH_COLOR = "#eb0028"  # Red
    NEUTRAL_COLOR = "#999999"  # Gray

    def extract_trend_ranges_from_html(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Extract trend ranges from ETF Pro Plus HTML email content

        Args:
            html_content: Raw HTML email content from ETF Pro Plus emails

        Returns:
            List of trend range dictionaries
        """
        try:
            if not html_content:
                logger.debug("No HTML content provided")
                return []

            soup = BeautifulSoup(html_content, "html.parser")
            trend_ranges = []

            # Find all tables in the email
            tables = soup.find_all("table")

            for table in tables:
                # Check if this table contains ETF Pro Plus trend range data
                if self._is_trend_range_table(table):
                    ranges = self._extract_trend_ranges_from_table(table)
                    trend_ranges.extend(ranges)

            logger.info(f"Extracted {len(trend_ranges)} trend ranges from HTML")
            return trend_ranges

        except Exception as e:
            logger.error(f"Error extracting trend ranges from HTML: {e}")
            return []

    def _is_trend_range_table(self, table) -> bool:
        """
        Check if a table contains ETF Pro Plus trend range data

        Args:
            table: BeautifulSoup table element

        Returns:
            True if table contains trend range data
        """
        try:
            # Convert table to text and check for key indicators
            table_text = table.get_text().upper()

            # Check for headers that indicate ETF Pro Plus trend range data
            has_ticker = "TICKER" in table_text
            has_recent_price = "RECENT PRICE" in table_text
            has_trend_ranges = "TREND RANGES" in table_text or "TREND RANGE" in table_text

            # Check for section headers
            has_bullish_section = "BULLISH" in table_text
            has_bearish_section = "BEARISH" in table_text

            # Must have core columns and section indicators
            return (has_ticker and has_recent_price and has_trend_ranges) or (
                has_bullish_section or has_bearish_section
            )

        except Exception:
            return False

    def _extract_trend_ranges_from_table(self, table) -> List[Dict[str, Any]]:
        """
        Extract trend range data from a single table

        Args:
            table: BeautifulSoup table element

        Returns:
            List of trend range dictionaries
        """
        ranges = []

        try:
            # Determine if this is a BULLISH or BEARISH section
            table_text = table.get_text().upper()
            section_trend = (
                "BULLISH" if "BULLISH" in table_text else ("BEARISH" if "BEARISH" in table_text else "UNKNOWN")
            )

            rows = table.find_all("tr")

            # Find header row to determine column positions
            header_row = None
            header_index = -1

            for i, row in enumerate(rows):
                row_text = row.get_text().upper()
                if any(header in row_text for header in ["TICKER", "DATE ADDED", "RECENT PRICE", "TREND RANGE"]):
                    header_row = row
                    header_index = i
                    break

            if header_row is None:
                # Try to find data rows without explicit headers
                for i, row in enumerate(rows):
                    if self._looks_like_data_row(row):
                        # Assume standard column order: Name, Ticker, Date, Price, Range Low, Range High, Asset Class
                        range_data = self._extract_trend_range_from_row_without_header(row, section_trend)
                        if range_data:
                            ranges.append(range_data)
                return ranges

            # Determine column indices
            headers = header_row.find_all(["th", "td"])
            col_indices = self._get_trend_column_indices(headers)

            if not col_indices:
                return ranges

            # Process data rows (skip header row)
            for row in rows[header_index + 1 :]:
                cells = row.find_all(["td", "th"])

                if len(cells) < 3:  # Minimum viable row
                    continue

                range_data = self._extract_trend_range_from_row(cells, col_indices, section_trend)
                if range_data:
                    ranges.append(range_data)

        except Exception as e:
            logger.error(f"Error extracting trend ranges from table: {e}")

        return ranges

    def _looks_like_data_row(self, row) -> bool:
        """
        Check if a row looks like it contains data (has ticker-like text and prices)
        """
        try:
            row_text = row.get_text().strip()
            # Look for patterns like ticker symbols and prices
            has_ticker_pattern = bool(re.search(r"\b[A-Z]{2,5}\b", row_text))
            has_price_pattern = bool(re.search(r"\$\d+\.\d+", row_text))
            has_date_pattern = bool(re.search(r"\d{1,2}/\d{1,2}/\d{4}", row_text))

            return has_ticker_pattern and (has_price_pattern or has_date_pattern)
        except Exception:
            return False

    def _get_trend_column_indices(self, headers) -> Dict[str, int]:
        """
        Determine column indices for trend range data extraction

        Args:
            headers: List of header cells

        Returns:
            Dictionary mapping column names to indices
        """
        indices = {}

        for i, header in enumerate(headers):
            header_text = header.get_text().strip().upper()

            if "TICKER" in header_text:
                indices["ticker"] = i
            elif "DATE" in header_text and "ADDED" in header_text:
                indices["date_added"] = i
            elif "RECENT" in header_text and "PRICE" in header_text:
                indices["recent_price"] = i
            elif "TREND" in header_text and "RANGE" in header_text:
                indices["trend_range"] = i
                # If TREND RANGES is found, check if the data is split into two columns after it
                if i + 1 < len(headers):
                    indices["range_low"] = i
                    indices["range_high"] = i + 1
            elif "ASSET" in header_text and "CLASS" in header_text:
                indices["asset_class"] = i
            elif header_text.startswith("$") and i > 2:  # Range columns often start with $
                if "range_low" not in indices:
                    indices["range_low"] = i
                elif "range_high" not in indices:
                    indices["range_high"] = i

        # Special handling for ETF Pro Plus format where TREND RANGES data spans multiple columns
        # If we found a trend_range column, assume the data is split across the current and next column
        if "trend_range" in indices:
            # For ETF Pro Plus, TREND RANGES spans two columns
            indices["range_low"] = indices["trend_range"]
            if indices["trend_range"] + 1 < len(headers):
                indices["range_high"] = indices["trend_range"] + 1

            # If asset_class was detected but conflicts with range columns, move it
            if "asset_class" in indices:
                if indices["asset_class"] == indices["range_high"]:
                    # Asset class is actually in the next column
                    indices["asset_class"] = indices["range_high"] + 1
                elif indices["asset_class"] == indices["range_low"]:
                    # Asset class is actually further out
                    indices["asset_class"] = indices["range_high"] + 1

        # Validate we have minimum required columns
        if "ticker" in indices and ("trend_range" in indices or ("range_low" in indices and "range_high" in indices)):
            return indices

        # Alternative: Try to guess based on position if headers aren't clear
        if len(headers) >= 5:
            return {
                "name": 0,
                "ticker": 1,
                "date_added": 2,
                "recent_price": 3,
                "range_low": 4,
                "range_high": 5,
                "asset_class": 6 if len(headers) > 6 else 0,
            }

        return {}

    def _extract_trend_range_from_row(
        self, cells, col_indices: Dict[str, int], section_trend: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract trend range data from a table row with known column indices

        Args:
            cells: List of cell elements in the row
            col_indices: Dictionary mapping column names to indices
            section_trend: BULLISH or BEARISH section indicator

        Returns:
            Trend range dictionary or None if extraction fails
        """
        try:
            # Check if row has minimum required cells
            required_indices = ["ticker"]
            max_index = max(col_indices.get(col, -1) for col in required_indices if col in col_indices)

            # Also check for range columns
            if "range_low" in col_indices and "range_high" in col_indices:
                max_index = max(max_index, col_indices["range_low"], col_indices["range_high"])
            elif "trend_range" in col_indices:
                max_index = max(max_index, col_indices["trend_range"])

            if max_index >= len(cells):
                # Row doesn't have enough cells
                return None

            # Extract ticker symbol
            ticker_cell = cells[col_indices["ticker"]]
            ticker = ticker_cell.get_text().strip().upper()

            # Clean ticker (remove any extra characters)
            ticker_match = re.match(r"^([A-Z0-9]+)", ticker)
            if not ticker_match:
                return None

            original_ticker = ticker_match.group(1)

            # Apply symbol mapping
            symbol_mapping_service = SymbolMappingService()
            etf_symbol = symbol_mapping_service.map_symbol(original_ticker)

            # Extract date added if available
            date_added = None
            if "date_added" in col_indices and col_indices["date_added"] < len(cells):
                date_cell = cells[col_indices["date_added"]]
                date_added = self._parse_date(date_cell.get_text().strip())

            # Extract recent price
            recent_price = None
            if "recent_price" in col_indices and col_indices["recent_price"] < len(cells):
                price_cell = cells[col_indices["recent_price"]]
                recent_price = self._extract_numeric_value(price_cell.get_text())

            # Extract trend range (could be combined or separate columns)
            range_low = None
            range_high = None

            # Prefer separate columns if available
            if "range_low" in col_indices and "range_high" in col_indices:
                # Separate columns for low and high
                if col_indices["range_low"] < len(cells):
                    low_cell = cells[col_indices["range_low"]]
                    range_low = self._extract_numeric_value(low_cell.get_text())
                if col_indices["range_high"] < len(cells):
                    high_cell = cells[col_indices["range_high"]]
                    range_high = self._extract_numeric_value(high_cell.get_text())
            elif "trend_range" in col_indices and col_indices["trend_range"] < len(cells):
                # Combined range format like "$20.31$20.41" or "$20.31-$20.41"
                range_cell = cells[col_indices["trend_range"]]
                range_text = range_cell.get_text().strip()
                range_low, range_high = self._parse_combined_range(range_text)

            # Extract asset class
            asset_class = None
            if "asset_class" in col_indices and col_indices["asset_class"] and col_indices["asset_class"] < len(cells):
                asset_cell = cells[col_indices["asset_class"]]
                asset_class = asset_cell.get_text().strip()

            # Validate extracted data
            if not etf_symbol or range_low is None or range_high is None:
                logger.debug(f"Invalid trend range data: symbol={etf_symbol}, low={range_low}, high={range_high}")
                return None

            return {
                "original_symbol": original_ticker,  # Original symbol before mapping
                "etf_symbol": etf_symbol,  # Mapped symbol
                "trend": section_trend,
                "range_low": str(range_low),
                "range_high": str(range_high),
                "recent_price": str(recent_price) if recent_price is not None else None,
                "date_added": date_added,
                "asset_class": asset_class,
                "source": "gmail_hedgeye_etf_pro_plus",
            }

        except Exception as e:
            logger.debug(f"Error extracting trend range from row: {e}")
            return None

    def _extract_trend_range_from_row_without_header(self, row, section_trend: str) -> Optional[Dict[str, Any]]:
        """
        Extract trend range data from a row when headers are not clear
        Assumes standard order: Name, Ticker, Date, Price, Range Low, Range High, Asset Class
        """
        try:
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                return None

            # Try to find ticker in the first few cells
            ticker = None
            ticker_index = 0
            for i in range(min(3, len(cells))):
                cell_text = cells[i].get_text().strip().upper()
                ticker_match = re.match(r"^([A-Z]{2,6})$", cell_text)
                if ticker_match:
                    ticker = ticker_match.group(1)
                    ticker_index = i
                    break

            if not ticker:
                return None

            # Apply symbol mapping
            symbol_mapping_service = SymbolMappingService()
            etf_symbol = symbol_mapping_service.map_symbol(ticker)

            # Extract remaining data based on position relative to ticker
            recent_price = None
            range_low = None
            range_high = None

            # Look for price patterns after ticker
            for i in range(ticker_index + 1, len(cells)):
                cell_text = cells[i].get_text().strip()
                price_value = self._extract_numeric_value(cell_text)

                if price_value is not None:
                    if recent_price is None:
                        recent_price = price_value
                    elif range_low is None:
                        range_low = price_value
                    elif range_high is None:
                        range_high = price_value
                        break

            if range_low is None or range_high is None:
                return None

            return {
                "original_symbol": ticker,  # Original symbol before mapping
                "etf_symbol": etf_symbol,  # Mapped symbol
                "trend": section_trend,
                "range_low": str(range_low),
                "range_high": str(range_high),
                "recent_price": str(recent_price) if recent_price is not None else None,
                "date_added": None,
                "asset_class": None,
                "source": "gmail_hedgeye_etf_pro_plus",
            }

        except Exception as e:
            logger.debug(f"Error extracting trend range without header: {e}")
            return None

    def _parse_combined_range(self, range_text: str) -> tuple[Optional[float], Optional[float]]:
        """
        Parse combined range text like "$20.31$20.41" or "$20.31-$20.41"

        Returns:
            Tuple of (low, high) values
        """
        try:
            if not range_text:
                return None, None

            # First try to find patterns with separators in the original text
            for separator in ["-", "–", "—", " to ", " - ", " "]:
                if separator in range_text:
                    parts = range_text.split(separator, 1)
                    if len(parts) == 2:
                        low = self._extract_numeric_value(parts[0])
                        high = self._extract_numeric_value(parts[1])
                        if low is not None and high is not None:
                            return low, high

            # Try to find two consecutive price patterns in original text
            # Look for patterns like $20.31$20.41 or 20.3120.41
            price_pattern = r"\$?(\d+\.\d+)"
            matches = re.findall(price_pattern, range_text)
            if len(matches) >= 2:
                low = float(matches[0])
                high = float(matches[1])
                return low, high

            # Try a more specific pattern for concatenated dollar amounts
            concatenated_pattern = r"\$(\d+\.\d+)\$(\d+\.\d+)"
            match = re.search(concatenated_pattern, range_text)
            if match:
                low = float(match.group(1))
                high = float(match.group(2))
                return low, high

            # Try pattern for space-separated dollar amounts
            space_pattern = r"\$(\d+\.\d+)\s+\$(\d+\.\d+)"
            match = re.search(space_pattern, range_text)
            if match:
                low = float(match.group(1))
                high = float(match.group(2))
                return low, high

            return None, None

        except Exception:
            return None, None

    def _parse_date(self, date_text: str) -> Optional[str]:
        """
        Parse date from various formats and return ISO format
        """
        try:
            if not date_text:
                return None

            # Try common date formats
            for fmt in ["%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%m-%d-%Y"]:
                try:
                    parsed_date = datetime.datetime.strptime(date_text, fmt)
                    return parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    continue

            return None

        except Exception:
            return None

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

    def validate_extracted_data(self, trend_ranges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate and clean extracted trend range data

        Args:
            trend_ranges: List of extracted trend ranges

        Returns:
            List of validated trend ranges
        """
        validated = []

        for range_data in trend_ranges:
            try:
                # Ensure required fields are present
                if not all(key in range_data for key in ["etf_symbol", "range_low", "range_high"]):
                    continue

                # Validate ETF symbol format
                if not re.match(r"^[A-Z0-9]{1,10}$", range_data["etf_symbol"]):
                    continue

                # Validate numeric values
                try:
                    low_val = float(range_data["range_low"])
                    high_val = float(range_data["range_high"])
                    if low_val <= 0 or high_val <= 0:
                        continue

                    # Ensure low is less than high
                    if low_val >= high_val:
                        logger.warning(f"Low >= High for {range_data['etf_symbol']}: {low_val} >= {high_val}")
                        continue
                except (ValueError, TypeError):
                    continue

                validated.append(range_data)

            except Exception as e:
                logger.debug(f"Validation error for trend range data: {e}")
                continue

        return validated
