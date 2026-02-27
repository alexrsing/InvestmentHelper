# Trading Recommendations Design

## Overview

Add backend-computed trading recommendations to each portfolio position based on risk range penetration and position sizing rules. The frontend displays the recommendation from the API instead of computing signals locally.

## Recommendation Signals

| Signal | Condition |
|--------|-----------|
| **Buy** | Penetration < 30% AND position weight < max_position_pct |
| **Sell** | Penetration > 70% |
| **Hold** | Penetration < 30% BUT position weight >= max_position_pct |
| **Stay** | Penetration between 30%-70% |

If risk range data is missing, recommendation is `null`.

Penetration formula: `(current_price - risk_range_low) / (risk_range_high - risk_range_low) * 100`

Thresholds (30%/70%) are fixed, not user-configurable.

## Backend Changes

### New file: `backend/app/services/recommendation_service.py`

Pure function that computes a recommendation for a single position:

```python
def compute_recommendation(
    current_price: float,
    risk_range_low: float,
    risk_range_high: float,
    position_weight: float,
    max_position_pct: float,
) -> str:  # "Buy" | "Sell" | "Hold" | "Stay"
```

### Modified: `backend/app/schemas/portfolio.py`

Add `recommendation: Optional[str] = None` to `PositionResponse`.

### Modified: `backend/app/routers/portfolio.py`

- After building positions and computing `total_value`, calculate each position's weight
- Fetch user's `TradingRules` (or use default `max_position_pct`)
- Call `compute_recommendation()` for each position with complete data
- Set the `recommendation` field on each `PositionResponse`

## Frontend Changes

### Modified: `frontend/src/types/index.ts`

Add `recommendation: string | null` to `ETFPosition`.

### Modified: `frontend/src/components/etf/ETFRow.tsx`

- Display the backend `recommendation` field instead of computing via `getSignal()`
- Color coding: Buy = green, Sell = red, Hold = yellow, Stay = blue
- Remove inline "Max Size" warning (replaced by "Hold" signal)

### Modified: `frontend/src/components/etf/RiskBar.tsx`

- `getSignal()` can be removed since the backend is the source of truth
- The visual penetration bar remains unchanged
