import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from pynamodb.exceptions import DoesNotExist

from app.services.trade_service import execute_trade, get_todays_decisions, get_trade_history, clear_todays_decisions


USER_ID = "test-user-123"
TICKER = "SPY"
TODAY = "2026-02-28"


def _make_portfolio(shares=10.0, cash=5000.0, initial_value=10000.0, ticker=TICKER):
    portfolio = MagicMock()
    holding = MagicMock()
    holding.ticker = ticker
    holding.shares = shares
    portfolio.holdings = [holding]
    portfolio.cash_balance = cash
    portfolio.initial_value = initial_value
    return portfolio


def _make_etf(price=100.0):
    etf = MagicMock()
    etf.current_price = price
    return etf


@patch("app.services.trade_service._today_str", return_value=TODAY)
@patch("app.services.trade_service.TradeDecision")
@patch("app.services.trade_service.ETF")
@patch("app.services.trade_service.Portfolio")
def test_buy_accepted(mock_portfolio_cls, mock_etf_cls, mock_decision_cls, mock_today):
    portfolio = _make_portfolio(shares=10, cash=5000)
    mock_portfolio_cls.get.return_value = portfolio
    mock_etf_cls.get.return_value = _make_etf(price=100)
    mock_decision_cls.get.side_effect = DoesNotExist()

    saved_decisions = []
    mock_decision_cls.side_effect = lambda **kwargs: _capture_decision(kwargs, saved_decisions)

    result = execute_trade(USER_ID, TICKER, "Buy", "accepted", 5.0)

    # Shares increase, cash decreases, initial_value increases
    assert portfolio.holdings[0].shares == 15.0
    assert portfolio.cash_balance == 4500.0
    assert portfolio.initial_value == 10500.0  # 10000 + (5 * 100)
    portfolio.save.assert_called_once()
    assert result.position_before == 10.0
    assert result.position_after == 15.0
    assert result.cash_before == 5000.0
    assert result.cash_after == 4500.0


@patch("app.services.trade_service._today_str", return_value=TODAY)
@patch("app.services.trade_service.TradeDecision")
@patch("app.services.trade_service.ETF")
@patch("app.services.trade_service.Portfolio")
def test_sell_accepted(mock_portfolio_cls, mock_etf_cls, mock_decision_cls, mock_today):
    portfolio = _make_portfolio(shares=10, cash=5000)
    mock_portfolio_cls.get.return_value = portfolio
    mock_etf_cls.get.return_value = _make_etf(price=100)
    mock_decision_cls.get.side_effect = DoesNotExist()

    saved_decisions = []
    mock_decision_cls.side_effect = lambda **kwargs: _capture_decision(kwargs, saved_decisions)

    result = execute_trade(USER_ID, TICKER, "Sell", "accepted", 3.0)

    # Shares decrease, cash increases, initial_value decreases
    assert portfolio.holdings[0].shares == 7.0
    assert portfolio.cash_balance == 5300.0
    assert portfolio.initial_value == 9700.0  # 10000 - (3 * 100)
    portfolio.save.assert_called_once()
    assert result.position_before == 10.0
    assert result.position_after == 7.0
    assert result.cash_before == 5000.0
    assert result.cash_after == 5300.0


@patch("app.services.trade_service._today_str", return_value=TODAY)
@patch("app.services.trade_service.TradeDecision")
@patch("app.services.trade_service.ETF")
@patch("app.services.trade_service.Portfolio")
def test_decline_no_portfolio_change(mock_portfolio_cls, mock_etf_cls, mock_decision_cls, mock_today):
    portfolio = _make_portfolio(shares=10, cash=5000)
    mock_portfolio_cls.get.return_value = portfolio
    mock_etf_cls.get.return_value = _make_etf(price=100)
    mock_decision_cls.get.side_effect = DoesNotExist()

    saved_decisions = []
    mock_decision_cls.side_effect = lambda **kwargs: _capture_decision(kwargs, saved_decisions)

    result = execute_trade(USER_ID, TICKER, "Buy", "declined", 5.0)

    # Portfolio unchanged (including initial_value)
    portfolio.save.assert_not_called()
    assert portfolio.initial_value == 10000.0
    assert result.position_before == 10.0
    assert result.position_after == 10.0
    assert result.cash_before == 5000.0
    assert result.cash_after == 5000.0
    assert result.action == "declined"


@patch("app.services.trade_service._today_str", return_value=TODAY)
@patch("app.services.trade_service.TradeDecision")
def test_idempotency_rejects_duplicate(mock_decision_cls, mock_today):
    mock_decision_cls.get.return_value = MagicMock()  # Already exists

    with pytest.raises(ValueError, match="already recorded"):
        execute_trade(USER_ID, TICKER, "Buy", "accepted", 5.0)


@patch("app.services.trade_service._today_str", return_value=TODAY)
@patch("app.services.trade_service.TradeDecision")
@patch("app.services.trade_service.ETF")
@patch("app.services.trade_service.Portfolio")
def test_buy_exceeds_cash(mock_portfolio_cls, mock_etf_cls, mock_decision_cls, mock_today):
    portfolio = _make_portfolio(shares=10, cash=100)
    mock_portfolio_cls.get.return_value = portfolio
    mock_etf_cls.get.return_value = _make_etf(price=100)
    mock_decision_cls.get.side_effect = DoesNotExist()

    with pytest.raises(ValueError, match="Insufficient cash"):
        execute_trade(USER_ID, TICKER, "Buy", "accepted", 5.0)


@patch("app.services.trade_service._today_str", return_value=TODAY)
@patch("app.services.trade_service.TradeDecision")
@patch("app.services.trade_service.ETF")
@patch("app.services.trade_service.Portfolio")
def test_sell_exceeds_holdings(mock_portfolio_cls, mock_etf_cls, mock_decision_cls, mock_today):
    portfolio = _make_portfolio(shares=3, cash=5000)
    mock_portfolio_cls.get.return_value = portfolio
    mock_etf_cls.get.return_value = _make_etf(price=100)
    mock_decision_cls.get.side_effect = DoesNotExist()

    with pytest.raises(ValueError, match="Insufficient shares"):
        execute_trade(USER_ID, TICKER, "Sell", "accepted", 5.0)


@patch("app.services.trade_service._today_str", return_value=TODAY)
@patch("app.services.trade_service.TradeDecision")
def test_get_todays_decisions(mock_decision_cls, mock_today):
    item1 = MagicMock()
    item1.ticker = "SPY"
    item2 = MagicMock()
    item2.ticker = "QQQ"
    mock_decision_cls.query.return_value = [item1, item2]

    result = get_todays_decisions(USER_ID)

    assert "SPY" in result
    assert "QQQ" in result
    assert len(result) == 2
    mock_decision_cls.query.assert_called_once()


@patch("app.services.trade_service.TradeDecision")
def test_get_trade_history(mock_decision_cls):
    items = [MagicMock(), MagicMock(), MagicMock()]
    mock_decision_cls.query.return_value = items

    result = get_trade_history(USER_ID, limit=50)

    assert len(result) == 3
    mock_decision_cls.query.assert_called_once_with(
        USER_ID,
        scan_index_forward=False,
        limit=50,
    )


@patch("app.services.trade_service._today_str", return_value=TODAY)
@patch("app.services.trade_service.TradeDecision")
def test_clear_todays_decisions(mock_decision_cls, mock_today):
    item1, item2 = MagicMock(), MagicMock()
    mock_decision_cls.query.return_value = [item1, item2]
    batch_ctx = MagicMock()
    mock_decision_cls.batch_write.return_value.__enter__ = MagicMock(return_value=batch_ctx)
    mock_decision_cls.batch_write.return_value.__exit__ = MagicMock(return_value=False)

    count = clear_todays_decisions(USER_ID)

    assert count == 2
    assert batch_ctx.delete.call_count == 2


@patch("app.services.trade_service._today_str", return_value=TODAY)
@patch("app.services.trade_service.TradeDecision")
def test_clear_todays_decisions_empty(mock_decision_cls, mock_today):
    mock_decision_cls.query.return_value = []
    batch_ctx = MagicMock()
    mock_decision_cls.batch_write.return_value.__enter__ = MagicMock(return_value=batch_ctx)
    mock_decision_cls.batch_write.return_value.__exit__ = MagicMock(return_value=False)

    count = clear_todays_decisions(USER_ID)

    assert count == 0
    batch_ctx.delete.assert_not_called()


def _capture_decision(kwargs, container):
    """Helper that creates a mock TradeDecision with the given attributes."""
    decision = MagicMock()
    for k, v in kwargs.items():
        setattr(decision, k, v)
    container.append(decision)
    return decision
