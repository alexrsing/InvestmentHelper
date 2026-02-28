BUY_THRESHOLD = 30.0
SELL_THRESHOLD = 70.0


def compute_recommendation(
    current_price: float,
    risk_range_low: float,
    risk_range_high: float,
    position_weight: float,
    max_position_pct: float,
    min_position_pct: float,
) -> str:
    """Compute a trading recommendation for a single position.

    Returns one of: "Buy", "Sell", "Hold", "Stay"
    """
    range_size = risk_range_high - risk_range_low
    penetration = ((current_price - risk_range_low) / range_size) * 100
    penetration = max(0.0, min(100.0, penetration))

    if penetration < BUY_THRESHOLD:
        if position_weight >= max_position_pct:
            return "Hold"
        return "Buy"

    if penetration > SELL_THRESHOLD:
        if min_position_pct > 0 and position_weight < min_position_pct:
            return "Hold"
        return "Sell"

    return "Stay"
