from app.services.recommendation_service import compute_recommendation


def test_buy_signal_low_penetration_under_max_size():
    result = compute_recommendation(
        current_price=100.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        position_weight=1.5,
        max_position_pct=2.5,
    )
    # penetration = (100-95)/(115-95) = 25% -> Buy zone
    assert result == "Buy"


def test_hold_signal_low_penetration_at_max_size():
    result = compute_recommendation(
        current_price=100.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        position_weight=2.5,
        max_position_pct=2.5,
    )
    # penetration = 25% -> Buy zone, but weight >= max -> Hold
    assert result == "Hold"


def test_hold_signal_low_penetration_over_max_size():
    result = compute_recommendation(
        current_price=100.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        position_weight=3.0,
        max_position_pct=2.5,
    )
    assert result == "Hold"


def test_sell_signal_high_penetration():
    result = compute_recommendation(
        current_price=112.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        position_weight=1.5,
        max_position_pct=2.5,
    )
    # penetration = (112-95)/(115-95) = 85% -> Sell zone
    assert result == "Sell"


def test_stay_signal_mid_penetration():
    result = compute_recommendation(
        current_price=105.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        position_weight=1.5,
        max_position_pct=2.5,
    )
    # penetration = (105-95)/(115-95) = 50% -> Stay zone
    assert result == "Stay"


def test_buy_at_exactly_30_percent():
    result = compute_recommendation(
        current_price=101.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        position_weight=1.0,
        max_position_pct=2.5,
    )
    # penetration = (101-95)/(115-95) = 30% -> boundary, should be Stay
    assert result == "Stay"


def test_sell_at_exactly_70_percent():
    result = compute_recommendation(
        current_price=109.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        position_weight=1.0,
        max_position_pct=2.5,
    )
    # penetration = (109-95)/(115-95) = 70% -> boundary, should be Stay
    assert result == "Stay"


def test_price_below_risk_range():
    result = compute_recommendation(
        current_price=90.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        position_weight=1.0,
        max_position_pct=2.5,
    )
    # penetration clamped to 0% -> Buy zone
    assert result == "Buy"


def test_price_above_risk_range():
    result = compute_recommendation(
        current_price=120.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        position_weight=1.0,
        max_position_pct=2.5,
    )
    # penetration clamped to 100% -> Sell zone
    assert result == "Sell"
