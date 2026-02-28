from dataclasses import dataclass

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
