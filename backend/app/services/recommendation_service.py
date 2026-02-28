from dataclasses import dataclass
from copy import deepcopy

BUY_THRESHOLD = 30.0
SELL_THRESHOLD = 70.0


@dataclass
class Recommendation:
    signal: str  # "Buy", "Sell", "Hold", "Stay"
    shares_to_trade: float  # positive shares to buy/sell, 0 for Hold/Stay
    target_position_value: float  # dollar value after trade
    current_position_value: float  # dollar value before trade
    penetration_depth: float  # 0.0-1.0 zone-specific depth ratio


def _hold(current_position_value: float) -> Recommendation:
    return Recommendation(
        signal="Hold",
        shares_to_trade=0,
        target_position_value=current_position_value,
        current_position_value=current_position_value,
        penetration_depth=0.0,
    )


def compute_recommendation(
    current_price: float,
    risk_range_low: float,
    risk_range_high: float,
    current_position_value: float,
    portfolio_value: float,
    max_position_pct: float,
    min_position_pct: float,
) -> Recommendation:
    """Compute a trading recommendation for a single position.

    Returns a Recommendation with signal, shares_to_trade, target_position_value,
    current_position_value, and penetration_depth.
    """
    range_size = risk_range_high - risk_range_low
    if range_size <= 0 or current_price <= 0:
        return _hold(current_position_value)

    penetration = ((current_price - risk_range_low) / range_size) * 100
    penetration = max(0.0, min(100.0, penetration))

    max_position_value = portfolio_value * max_position_pct / 100
    min_position_value = portfolio_value * min_position_pct / 100

    if penetration < BUY_THRESHOLD:
        if current_position_value >= max_position_value:
            return _hold(current_position_value)

        buy_zone_top = risk_range_low + (BUY_THRESHOLD / 100) * range_size
        buy_depth = (buy_zone_top - current_price) / (buy_zone_top - risk_range_low)
        buy_depth = max(0.0, min(1.0, buy_depth))

        target = current_position_value + buy_depth * (max_position_value - current_position_value)
        target = min(target, max_position_value)

        shares_to_buy = (target - current_position_value) / current_price
        if shares_to_buy <= 0:
            return _hold(current_position_value)

        return Recommendation(
            signal="Buy",
            shares_to_trade=shares_to_buy,
            target_position_value=target,
            current_position_value=current_position_value,
            penetration_depth=buy_depth,
        )

    if penetration > SELL_THRESHOLD:
        if min_position_pct > 0 and current_position_value < min_position_value:
            return _hold(current_position_value)

        sell_zone_bottom = risk_range_low + (SELL_THRESHOLD / 100) * range_size
        sell_depth = (current_price - sell_zone_bottom) / (risk_range_high - sell_zone_bottom)
        sell_depth = max(0.0, min(1.0, sell_depth))

        target = current_position_value - sell_depth * (current_position_value - min_position_value)
        target = max(target, min_position_value)

        shares_to_sell = (current_position_value - target) / current_price
        if shares_to_sell <= 0:
            return _hold(current_position_value)

        return Recommendation(
            signal="Sell",
            shares_to_trade=shares_to_sell,
            target_position_value=target,
            current_position_value=current_position_value,
            penetration_depth=sell_depth,
        )

    return Recommendation(
        signal="Stay",
        shares_to_trade=0,
        target_position_value=current_position_value,
        current_position_value=current_position_value,
        penetration_depth=0.0,
    )


@dataclass
class PositionRecommendation:
    ticker: str
    current_price: float
    recommendation: Recommendation


def apply_cash_cap(
    position_recs: list[PositionRecommendation],
    cash_balance: float,
) -> list[PositionRecommendation]:
    """Cap buy recommendations so total buy cost does not exceed available cash.

    Distributes cash proportionally across buy signals. Converts buys to Hold
    if the allocated shares would be < 0.001.
    """
    if not position_recs:
        return []

    cash = max(0.0, cash_balance)
    result = deepcopy(position_recs)

    buy_indices = [
        i for i, pr in enumerate(result)
        if pr.recommendation.signal == "Buy"
    ]

    if not buy_indices:
        return result

    buy_costs = []
    for i in buy_indices:
        rec = result[i].recommendation
        cost = rec.shares_to_trade * result[i].current_price
        buy_costs.append(cost)

    total_buy_cost = sum(buy_costs)

    if total_buy_cost <= 0:
        return result

    if total_buy_cost <= cash:
        return result

    for j, i in enumerate(buy_indices):
        pr = result[i]
        rec = pr.recommendation

        if total_buy_cost > 0:
            allocated_cash = (buy_costs[j] / total_buy_cost) * cash
        else:
            allocated_cash = 0.0

        new_shares = allocated_cash / pr.current_price

        if new_shares < 0.001:
            rec.signal = "Hold"
            rec.shares_to_trade = 0
            rec.target_position_value = rec.current_position_value
        else:
            rec.shares_to_trade = new_shares
            rec.target_position_value = rec.current_position_value + allocated_cash

    return result
