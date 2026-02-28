import pytest
from app.services.csv_service import parse_fidelity_csv


VALID_CSV_HEADER = (
    "Account Type,Account,Beginning mkt Value,Change in Investment,"
    "Ending mkt Value,Short Balance,Ending Net Value,Dividends This Period,"
    "Dividends Year to Date,Interest This Year,Interest Year to Date,"
    "Total This Period,Total Year to Date\n"
    "Cash Management (Individual),Z40390480,297.94,8.58,306.52,,,,,"
    "0.10,0.10,0.10,0.10\n"
    "\n"
)

HOLDINGS_HEADER = "Symbol/CUSIP,Description,Quantity,Price,Beginning Value,Ending Value,Cost Basis\n"


def _make_csv(*holding_lines: str) -> str:
    """Build a minimal Fidelity CSV with the given holding lines."""
    return VALID_CSV_HEADER + HOLDINGS_HEADER + "\n".join(holding_lines)


# --- Cash parsing tests ---


def test_spaxx_extracted_as_cash_balance():
    csv = _make_csv(
        "AMZN,AMAZON.COM INC,3.00,239.30,693.61,717.90,451.46",
        "SPAXX,FIDELITY GOVERNMENT MONEY MARKET,97.22,1.00,96.94,97.22,not applicable",
    )
    result = parse_fidelity_csv(csv)
    assert result.cash_balance == pytest.approx(97.22)


def test_cash_not_included_in_total_value():
    csv = _make_csv(
        "AMZN,AMAZON.COM INC,3.00,239.30,693.61,717.90,451.46",
        "SPAXX,FIDELITY GOVERNMENT MONEY MARKET,97.22,1.00,96.94,97.22,not applicable",
    )
    result = parse_fidelity_csv(csv)
    assert result.total_value == pytest.approx(717.90)


def test_cash_not_included_in_initial_value():
    csv = _make_csv(
        "AMZN,AMAZON.COM INC,3.00,239.30,693.61,717.90,451.46",
        "SPAXX,FIDELITY GOVERNMENT MONEY MARKET,97.22,1.00,96.94,97.22,not applicable",
    )
    result = parse_fidelity_csv(csv)
    assert result.initial_value == pytest.approx(451.46)


def test_zero_cash_when_no_money_market():
    csv = _make_csv(
        "AMZN,AMAZON.COM INC,3.00,239.30,693.61,717.90,451.46",
    )
    result = parse_fidelity_csv(csv)
    assert result.cash_balance == 0.0


def test_spaxx_not_in_holdings_list():
    csv = _make_csv(
        "AMZN,AMAZON.COM INC,3.00,239.30,693.61,717.90,451.46",
        "SPAXX,FIDELITY GOVERNMENT MONEY MARKET,97.22,1.00,96.94,97.22,not applicable",
    )
    result = parse_fidelity_csv(csv)
    tickers = [h.ticker for h in result.holdings]
    assert "SPAXX" not in tickers


def test_multiple_stocks_with_cash():
    csv = _make_csv(
        "AMZN,AMAZON.COM INC,3.00,239.30,693.61,717.90,451.46",
        "NVDA,NVIDIA CORPORATION COM,1.00,191.13,186.50,191.13,147.75",
        "SPAXX,FIDELITY GOVERNMENT MONEY MARKET,97.22,1.00,96.94,97.22,not applicable",
    )
    result = parse_fidelity_csv(csv)
    assert len(result.holdings) == 2
    assert result.cash_balance == pytest.approx(97.22)
    assert result.total_value == pytest.approx(717.90 + 191.13)
    assert result.initial_value == pytest.approx(451.46 + 147.75)


def test_case_insensitive_not_applicable():
    csv = _make_csv(
        "AMZN,AMAZON.COM INC,3.00,239.30,693.61,717.90,451.46",
        "SPAXX,FIDELITY GOVERNMENT MONEY MARKET,97.22,1.00,96.94,97.22,Not Applicable",
    )
    result = parse_fidelity_csv(csv)
    assert result.cash_balance == pytest.approx(97.22)
    assert "SPAXX" not in [h.ticker for h in result.holdings]


# --- Existing behavior preserved ---


def test_valid_csv_parses_holdings():
    csv = _make_csv(
        "AMZN,AMAZON.COM INC,3.00,239.30,693.61,717.90,451.46",
        "NVDA,NVIDIA CORPORATION COM,1.00,191.13,186.50,191.13,147.75",
    )
    result = parse_fidelity_csv(csv)
    assert len(result.holdings) == 2
    assert result.holdings[0].ticker == "AMZN"
    assert result.holdings[0].quantity == pytest.approx(3.0)
    assert result.holdings[0].cost_basis == pytest.approx(451.46)
    assert result.holdings[1].ticker == "NVDA"


def test_missing_header_raises():
    csv = "some random,data\nno,header,here\n"
    with pytest.raises(ValueError, match="missing Symbol/CUSIP header"):
        parse_fidelity_csv(csv)


def test_no_holdings_raises():
    csv = VALID_CSV_HEADER + HOLDINGS_HEADER + "\n"
    with pytest.raises(ValueError, match="No holdings found"):
        parse_fidelity_csv(csv)
