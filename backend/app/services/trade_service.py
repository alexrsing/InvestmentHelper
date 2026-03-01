from datetime import datetime, timezone

from pynamodb.exceptions import DoesNotExist

from app.models.trade_decision import TradeDecision
from app.models.portfolio import Portfolio
from app.models.etf import ETF


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def execute_trade(
    user_id: str,
    ticker: str,
    signal: str,
    action: str,
    shares: float,
) -> TradeDecision:
    today = _today_str()
    decision_key = f"{today}#{ticker}"

    # Idempotency check
    try:
        TradeDecision.get(user_id, decision_key)
        raise ValueError(f"Trade decision already recorded for {ticker} today")
    except DoesNotExist:
        pass

    # Fetch portfolio
    portfolio = Portfolio.get(user_id)

    # Find holding
    holding = None
    holding_idx = None
    for i, h in enumerate(portfolio.holdings):
        if h.ticker == ticker:
            holding = h
            holding_idx = i
            break

    if holding is None:
        raise ValueError(f"No holding found for {ticker}")

    # Fetch current price
    etf = ETF.get(ticker)
    price = etf.current_price
    if price is None or price <= 0:
        raise ValueError(f"No valid price for {ticker}")

    current_shares = float(holding.shares)
    cash_balance = float(portfolio.cash_balance or 0)

    position_before = current_shares
    cash_before = cash_balance

    if action == "accepted":
        if signal == "Buy":
            cost = shares * price
            if cost > cash_balance:
                raise ValueError(
                    f"Insufficient cash: need ${cost:.2f}, have ${cash_balance:.2f}"
                )
            new_shares = current_shares + shares
            new_cash = cash_balance - cost
        elif signal == "Sell":
            if shares > current_shares:
                raise ValueError(
                    f"Insufficient shares: want to sell {shares}, have {current_shares}"
                )
            new_shares = current_shares - shares
            new_cash = cash_balance + (shares * price)
        else:
            raise ValueError(f"Invalid signal: {signal}")

        portfolio.holdings[holding_idx].shares = new_shares
        portfolio.cash_balance = new_cash
        trade_amount = shares * price
        if signal == "Buy":
            portfolio.initial_value = float(portfolio.initial_value or 0) + trade_amount
        else:
            portfolio.initial_value = float(portfolio.initial_value or 0) - trade_amount
        portfolio.updated_at = datetime.now(timezone.utc)
        portfolio.save()

        position_after = new_shares
        cash_after = new_cash
    else:
        # Declined — no portfolio changes
        position_after = current_shares
        cash_after = cash_balance

    decision = TradeDecision(
        user_id=user_id,
        decision_key=decision_key,
        date=today,
        ticker=ticker,
        signal=signal,
        action=action,
        shares=shares,
        price=price,
        position_before=position_before,
        position_after=position_after,
        cash_before=cash_before,
        cash_after=cash_after,
    )
    decision.save()

    return decision


def get_todays_decisions(user_id: str) -> dict[str, TradeDecision]:
    today = _today_str()
    prefix = f"{today}#"
    results = {}
    for item in TradeDecision.query(user_id, TradeDecision.decision_key.startswith(prefix)):
        results[item.ticker] = item
    return results


def get_trade_history(user_id: str, limit: int = 200) -> list[TradeDecision]:
    results = []
    for item in TradeDecision.query(
        user_id,
        scan_index_forward=False,
        limit=limit,
    ):
        results.append(item)
    return results
