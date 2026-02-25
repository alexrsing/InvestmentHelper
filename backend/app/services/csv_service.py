import csv
from dataclasses import dataclass


@dataclass
class ParsedHolding:
    ticker: str
    quantity: float
    cost_basis: float


@dataclass
class ParsedPortfolio:
    holdings: list[ParsedHolding]
    total_value: float
    initial_value: float


def parse_fidelity_csv(content: str) -> ParsedPortfolio:
    """Parse a Fidelity portfolio statement CSV and extract holdings."""
    lines = content.splitlines()

    # Find the holdings header row
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Symbol/CUSIP"):
            header_idx = i
            break

    if header_idx is None:
        raise ValueError("Invalid Fidelity CSV: missing Symbol/CUSIP header")

    # Parse the holdings section
    holdings = []
    total_value = 0.0
    initial_value = 0.0

    reader = csv.reader(lines[header_idx + 1:])
    for row in reader:
        # Skip empty rows
        if not row or not row[0].strip():
            continue

        symbol = row[0].strip()

        # Skip non-data rows
        if symbol.startswith("Subtotal"):
            continue
        if symbol.startswith("Z"):  # Account number headers
            continue

        # Data rows have at least 7 columns and a valid quantity
        if len(row) < 7:
            continue

        try:
            quantity = float(row[2].strip())
            cost_basis = float(row[6].strip())
            ending_value = float(row[5].strip())
        except (ValueError, IndexError):
            continue

        holdings.append(ParsedHolding(
            ticker=symbol,
            quantity=quantity,
            cost_basis=cost_basis,
        ))
        total_value += ending_value
        initial_value += cost_basis

    if not holdings:
        raise ValueError("No holdings found in CSV")

    return ParsedPortfolio(
        holdings=holdings,
        total_value=total_value,
        initial_value=initial_value,
    )
