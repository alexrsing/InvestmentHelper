import pytest
from app.services.recommendation_service import compute_recommendation, Recommendation


PORTFOLIO_VALUE = 10000.0


def _call(current_price, risk_range_low, risk_range_high,
          position_weight, max_position_pct, min_position_pct=0.0):
    """Helper: converts old-style position_weight (%) to new params."""
    current_position_value = PORTFOLIO_VALUE * position_weight / 100
    return compute_recommendation(
        current_price=current_price,
        risk_range_low=risk_range_low,
        risk_range_high=risk_range_high,
        current_position_value=current_position_value,
        portfolio_value=PORTFOLIO_VALUE,
        max_position_pct=max_position_pct,
        min_position_pct=min_position_pct,
    )


# --- Existing signal tests (updated for Recommendation return type) ---


def test_buy_signal_low_penetration_under_max_size():
    result = _call(100.0, 95.0, 115.0, 1.5, 2.5)
    # penetration = (100-95)/(115-95) = 25% -> Buy zone
    assert result.signal == "Buy"


def test_hold_signal_low_penetration_at_max_size():
    result = _call(100.0, 95.0, 115.0, 2.5, 2.5)
    # penetration = 25% -> Buy zone, but weight >= max -> Hold
    assert result.signal == "Hold"


def test_hold_signal_low_penetration_over_max_size():
    result = _call(100.0, 95.0, 115.0, 3.0, 2.5)
    assert result.signal == "Hold"


def test_sell_signal_high_penetration():
    result = _call(112.0, 95.0, 115.0, 1.5, 2.5)
    # penetration = (112-95)/(115-95) = 85% -> Sell zone
    assert result.signal == "Sell"


def test_stay_signal_mid_penetration():
    result = _call(105.0, 95.0, 115.0, 1.5, 2.5)
    # penetration = (105-95)/(115-95) = 50% -> Stay zone
    assert result.signal == "Stay"


def test_buy_at_exactly_30_percent():
    result = _call(101.0, 95.0, 115.0, 1.0, 2.5)
    # penetration = (101-95)/(115-95) = 30% -> boundary, should be Stay
    assert result.signal == "Stay"


def test_sell_at_exactly_70_percent():
    result = _call(109.0, 95.0, 115.0, 1.0, 2.5)
    # penetration = (109-95)/(115-95) = 70% -> boundary, should be Stay
    assert result.signal == "Stay"


def test_price_below_risk_range():
    result = _call(90.0, 95.0, 115.0, 1.0, 2.5)
    # penetration clamped to 0% -> Buy zone
    assert result.signal == "Buy"


def test_price_above_risk_range():
    result = _call(120.0, 95.0, 115.0, 1.0, 2.5)
    # penetration clamped to 100% -> Sell zone
    assert result.signal == "Sell"


# --- Min position size tests ---


def test_hold_signal_high_penetration_under_min_size():
    result = _call(112.0, 95.0, 115.0, 0.5, 2.5, min_position_pct=1.0)
    # penetration = 85% -> Sell zone, but weight < min -> Hold
    assert result.signal == "Hold"


def test_sell_signal_high_penetration_min_disabled():
    result = _call(112.0, 95.0, 115.0, 0.5, 2.5, min_position_pct=0.0)
    # penetration = 85% -> Sell zone, min=0 (disabled) -> Sell
    assert result.signal == "Sell"


def test_sell_signal_high_penetration_above_min():
    result = _call(112.0, 95.0, 115.0, 1.5, 2.5, min_position_pct=1.0)
    # penetration = 85% -> Sell zone, weight > min -> Sell
    assert result.signal == "Sell"


def test_hold_signal_price_above_range_under_min():
    result = _call(120.0, 95.0, 115.0, 0.5, 2.5, min_position_pct=1.0)
    # penetration clamped to 100% -> Sell zone, but weight < min -> Hold
    assert result.signal == "Hold"


# --- Quantity tests ---


def test_buy_at_bottom_of_range_full_depth():
    # Price at risk_range_low -> depth=1.0, target should equal max_position_value
    result = compute_recommendation(
        current_price=95.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        current_position_value=150.0,
        portfolio_value=10000.0,
        max_position_pct=2.5,
        min_position_pct=0.0,
    )
    assert result.signal == "Buy"
    assert result.penetration_depth == pytest.approx(1.0)
    # target = 150 + 1.0 * (250 - 150) = 250
    assert result.target_position_value == pytest.approx(250.0)
    assert result.shares_to_trade == pytest.approx((250.0 - 150.0) / 95.0)
    assert result.current_position_value == pytest.approx(150.0)


def test_buy_at_midpoint_of_buy_zone():
    # buy_zone_top = 95 + 0.3 * 20 = 101, price=98 -> depth = (101-98)/(101-95) = 0.5
    result = compute_recommendation(
        current_price=98.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        current_position_value=150.0,
        portfolio_value=10000.0,
        max_position_pct=2.5,
        min_position_pct=0.0,
    )
    assert result.signal == "Buy"
    assert result.penetration_depth == pytest.approx(0.5)
    # target = 150 + 0.5 * (250 - 150) = 200
    assert result.target_position_value == pytest.approx(200.0)
    assert result.shares_to_trade == pytest.approx((200.0 - 150.0) / 98.0)


def test_buy_at_top_of_buy_zone_zero_depth():
    # Price just under 30% boundary: buy_zone_top=101, price ~= 101 -> depth ~= 0 -> Hold
    # penetration = (100.99 - 95) / 20 = 29.95% -> Buy zone
    # buy_depth = (101 - 100.99) / (101 - 95) = 0.01/6 ≈ 0.0017
    # shares_to_buy = very small but positive -> still Buy
    # Use exact boundary: price = buy_zone_top = 101, but that's 30% penetration = Stay
    # Instead use price that makes depth=0: price = buy_zone_top
    # Actually at penetration 29.99%, price = 95 + 0.2999*20 = 100.998
    # buy_depth = (101 - 100.998) / 6 = 0.0003 -> nearly 0 but positive
    # This will yield a tiny shares_to_buy > 0 so still "Buy" with small quantity
    result = compute_recommendation(
        current_price=100.998,
        risk_range_low=95.0,
        risk_range_high=115.0,
        current_position_value=150.0,
        portfolio_value=10000.0,
        max_position_pct=2.5,
        min_position_pct=0.0,
    )
    assert result.signal == "Buy"
    assert result.penetration_depth == pytest.approx(0.000333, abs=0.001)
    assert result.shares_to_trade == pytest.approx(0.0, abs=0.1)


def test_sell_at_top_of_range_full_depth():
    # Price at risk_range_high -> depth=1.0, target should equal min_position_value
    result = compute_recommendation(
        current_price=115.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        current_position_value=150.0,
        portfolio_value=10000.0,
        max_position_pct=2.5,
        min_position_pct=0.0,
    )
    assert result.signal == "Sell"
    assert result.penetration_depth == pytest.approx(1.0)
    # min_position_value = 0, target = 150 - 1.0 * (150 - 0) = 0
    assert result.target_position_value == pytest.approx(0.0)
    assert result.shares_to_trade == pytest.approx(150.0 / 115.0)


def test_sell_at_midpoint_of_sell_zone():
    # sell_zone_bottom = 95 + 0.7 * 20 = 109, price=112 -> depth = (112-109)/(115-109) = 0.5
    result = compute_recommendation(
        current_price=112.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        current_position_value=150.0,
        portfolio_value=10000.0,
        max_position_pct=2.5,
        min_position_pct=0.0,
    )
    assert result.signal == "Sell"
    assert result.penetration_depth == pytest.approx(0.5)
    # target = 150 - 0.5 * (150 - 0) = 75
    assert result.target_position_value == pytest.approx(75.0)
    assert result.shares_to_trade == pytest.approx((150.0 - 75.0) / 112.0)


def test_sell_at_bottom_of_sell_zone_zero_depth():
    # sell_zone_bottom = 109, price just above -> depth near 0 -> tiny sell
    # penetration = (109.01 - 95)/20 = 70.05% -> Sell zone
    # sell_depth = (109.01 - 109) / (115 - 109) = 0.01/6 ≈ 0.0017
    result = compute_recommendation(
        current_price=109.01,
        risk_range_low=95.0,
        risk_range_high=115.0,
        current_position_value=150.0,
        portfolio_value=10000.0,
        max_position_pct=2.5,
        min_position_pct=0.0,
    )
    assert result.signal == "Sell"
    assert result.penetration_depth == pytest.approx(0.0017, abs=0.001)
    assert result.shares_to_trade == pytest.approx(0.0, abs=0.1)


def test_stay_zone_quantity_fields_zero():
    result = compute_recommendation(
        current_price=105.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        current_position_value=150.0,
        portfolio_value=10000.0,
        max_position_pct=2.5,
        min_position_pct=0.0,
    )
    assert result.signal == "Stay"
    assert result.shares_to_trade == 0
    assert result.target_position_value == pytest.approx(150.0)
    assert result.penetration_depth == 0.0


def test_buy_when_already_at_max_value():
    # current_position_value == max_position_value -> Hold
    result = compute_recommendation(
        current_price=98.0,
        risk_range_low=95.0,
        risk_range_high=115.0,
        current_position_value=250.0,
        portfolio_value=10000.0,
        max_position_pct=2.5,
        min_position_pct=0.0,
    )
    assert result.signal == "Hold"
    assert result.shares_to_trade == 0
    assert result.target_position_value == pytest.approx(250.0)
    assert result.penetration_depth == 0.0
