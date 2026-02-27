# Trading Recommendations Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add backend-computed Buy/Sell/Hold/Stay recommendations to each portfolio position based on risk range penetration and position sizing rules.

**Architecture:** New `recommendation_service.py` computes signals per position. The portfolio endpoint fetches trading rules, calculates position weights, calls the service, and returns a `recommendation` field on each `PositionResponse`. Frontend displays the backend recommendation instead of computing signals locally.

**Tech Stack:** Python (FastAPI, PynamoDB, pytest), TypeScript (React)

---

### Task 1: Add pytest and create recommendation service tests

**Files:**
- Modify: `pyproject.toml` (add pytest to dev dependencies)
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_recommendation_service.py`

**Step 1: Add pytest dependency**

Run: `uv add --dev pytest`

**Step 2: Write failing tests for recommendation_service**

Create `backend/tests/__init__.py` (empty file).

Create `backend/tests/test_recommendation_service.py`:

```python
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
```

**Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_recommendation_service.py -v`
Expected: FAIL with `ModuleNotFoundError` (service doesn't exist yet)

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock backend/tests/
git commit -m "test: add recommendation service tests"
```

---

### Task 2: Implement recommendation service

**Files:**
- Create: `backend/app/services/recommendation_service.py`

**Step 1: Implement the service**

Create `backend/app/services/recommendation_service.py`:

```python
BUY_THRESHOLD = 30.0
SELL_THRESHOLD = 70.0


def compute_recommendation(
    current_price: float,
    risk_range_low: float,
    risk_range_high: float,
    position_weight: float,
    max_position_pct: float,
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
        return "Sell"

    return "Stay"
```

**Step 2: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_recommendation_service.py -v`
Expected: All 9 tests PASS

**Step 3: Commit**

```bash
git add backend/app/services/recommendation_service.py
git commit -m "feat: add recommendation service with penetration-based logic"
```

---

### Task 3: Add recommendation to portfolio schema

**Files:**
- Modify: `backend/app/schemas/portfolio.py:11-17` (PositionResponse)

**Step 1: Add recommendation field to PositionResponse**

In `backend/app/schemas/portfolio.py`, add to `PositionResponse`:

```python
class PositionResponse(BaseModel):
    ticker: str
    name: Optional[str] = None
    current_price: Optional[float] = None
    open_price: Optional[float] = None
    risk_range_low: Optional[float] = None
    risk_range_high: Optional[float] = None
    shares: float
    recommendation: Optional[str] = None
```

**Step 2: Commit**

```bash
git add backend/app/schemas/portfolio.py
git commit -m "feat: add recommendation field to PositionResponse schema"
```

---

### Task 4: Wire recommendation into portfolio endpoint

**Files:**
- Modify: `backend/app/routers/portfolio.py`

**Step 1: Update portfolio endpoint to compute recommendations**

Add imports at top of `backend/app/routers/portfolio.py`:

```python
from app.models.trading_rules import TradingRules, DEFAULT_MAX_POSITION_PCT
from app.services.recommendation_service import compute_recommendation
```

In `get_portfolio()`, after the for-loop that builds `positions` and computes `total_value` (after line 75), add logic to fetch trading rules and compute recommendations for each position:

```python
    # Fetch trading rules for position sizing
    try:
        rules = TradingRules.get(user_id)
        max_position_pct = float(rules.max_position_pct)
    except DoesNotExist:
        max_position_pct = DEFAULT_MAX_POSITION_PCT
    except Exception:
        max_position_pct = DEFAULT_MAX_POSITION_PCT

    # Compute recommendations
    for pos in positions:
        if (
            pos.current_price is not None
            and pos.risk_range_low is not None
            and pos.risk_range_high is not None
            and pos.risk_range_high - pos.risk_range_low > 0
            and total_value > 0
        ):
            position_value = pos.current_price * pos.shares
            position_weight = (position_value / total_value) * 100
            pos.recommendation = compute_recommendation(
                current_price=pos.current_price,
                risk_range_low=pos.risk_range_low,
                risk_range_high=pos.risk_range_high,
                position_weight=position_weight,
                max_position_pct=max_position_pct,
            )
```

**Step 2: Verify the backend starts without errors**

Run: `cd backend && python -c "from app.routers.portfolio import router; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/app/routers/portfolio.py
git commit -m "feat: compute recommendations in portfolio endpoint"
```

---

### Task 5: Update frontend types

**Files:**
- Modify: `frontend/src/types/index.ts:1-9` (ETFPosition)

**Step 1: Add recommendation to ETFPosition**

In `frontend/src/types/index.ts`, add to `ETFPosition`:

```typescript
export interface ETFPosition {
  ticker: string;
  name: string | null;
  current_price: number | null;
  open_price: number | null;
  risk_range_low: number | null;
  risk_range_high: number | null;
  shares: number;
  recommendation: string | null;
}
```

**Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add recommendation field to ETFPosition type"
```

---

### Task 6: Update ETFRow to display backend recommendation

**Files:**
- Modify: `frontend/src/components/etf/ETFRow.tsx`

**Step 1: Replace inline signal computation with backend recommendation**

Replace the import line and update the component. Key changes:
- Remove the `import RiskBar, { getSignal }` — change to just `import RiskBar`
- Use `position.recommendation` for the signal label and color
- Remove the inline `getSignal()` call and "Max Size" warning
- Add a color mapping function for the recommendation

Updated `ETFRow.tsx`:

```typescript
import type { ETFPosition } from "../../types";
import RiskBar from "./RiskBar";

interface Props {
  position: ETFPosition;
  onClick: (ticker: string) => void;
  totalValue: number;
  maxPositionPct: number | null;
}

function getRecommendationColor(rec: string): string {
  switch (rec) {
    case "Buy": return "text-green-400";
    case "Sell": return "text-red-400";
    case "Hold": return "text-yellow-400";
    case "Stay": return "text-blue-400";
    default: return "text-gray-400";
  }
}

export default function ETFRow({ position, onClick, totalValue, maxPositionPct }: Props) {
  const {
    ticker,
    name,
    current_price,
    open_price,
    risk_range_low,
    risk_range_high,
    recommendation,
  } = position;

  const fmt = (v: number | null) =>
    v != null
      ? v.toLocaleString("en-US", { style: "currency", currency: "USD" })
      : "—";

  const priceChange =
    current_price != null && open_price != null
      ? current_price - open_price
      : null;
  const changeColor =
    priceChange != null && priceChange >= 0 ? "text-green-400" : "text-red-400";

  const positionValue =
    current_price != null ? position.shares * current_price : null;

  const positionWeight =
    positionValue != null && totalValue > 0
      ? (positionValue / totalValue) * 100
      : null;

  const isMaxSize =
    positionWeight != null &&
    maxPositionPct != null &&
    positionWeight >= maxPositionPct;

  return (
    <button
      type="button"
      onClick={() => onClick(ticker)}
      className="w-full text-left border border-gray-800 rounded bg-[#161b22] hover:bg-[#1c2333] transition-colors p-4 cursor-pointer"
    >
      <div className="flex flex-col md:flex-row md:items-center gap-3">
        {/* Ticker + Name */}
        <div className="md:w-32 shrink-0">
          <span className="text-green-400 font-mono font-bold text-lg">
            {ticker}
          </span>
          {name && (
            <div className="text-xs text-gray-500 truncate">{name}</div>
          )}
        </div>

        {/* Prices */}
        <div className="flex gap-6 md:gap-8 flex-wrap md:flex-nowrap flex-1">
          <div>
            <div className="text-xs text-gray-500 uppercase">Current</div>
            <div className={`font-mono ${changeColor}`}>
              {fmt(current_price)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase">Open</div>
            <div className="font-mono text-gray-300">{fmt(open_price)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase">Risk Low</div>
            <div className="font-mono text-gray-300">
              {fmt(risk_range_low)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase">Risk High</div>
            <div className="font-mono text-gray-300">
              {fmt(risk_range_high)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase">Shares</div>
            <div className="font-mono text-gray-300">
              {position.shares}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase">Value</div>
            <div className="font-mono text-gray-300">
              {positionValue != null ? fmt(positionValue) : "—"}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase">Weight</div>
            <div className={`font-mono ${isMaxSize ? "text-yellow-400" : "text-gray-300"}`}>
              {positionWeight != null ? `${positionWeight.toFixed(1)}%` : "—"}
            </div>
          </div>
        </div>

        {/* Risk Bar */}
        <div className="md:w-48 shrink-0">
          <div className="text-xs uppercase mb-1">
            <span className="text-gray-500">Penetration</span>
            {recommendation && (
              <span className={`${getRecommendationColor(recommendation)} font-bold`}>
                {" · "}{recommendation}
              </span>
            )}
          </div>
          {risk_range_low != null &&
          risk_range_high != null &&
          current_price != null ? (
            <RiskBar
              low={risk_range_low}
              high={risk_range_high}
              current={current_price}
            />
          ) : (
            <span className="text-xs text-gray-600">—</span>
          )}
        </div>
      </div>
    </button>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/etf/ETFRow.tsx
git commit -m "feat: display backend recommendation instead of inline signal"
```

---

### Task 7: Clean up RiskBar (remove unused getSignal export)

**Files:**
- Modify: `frontend/src/components/etf/RiskBar.tsx`

**Step 1: Remove getSignal function**

`getSignal` is no longer used by any consumer. Remove it from `RiskBar.tsx`. The file becomes:

```typescript
interface Props {
  low: number;
  high: number;
  current: number;
}

export default function RiskBar({ low, high, current }: Props) {
  const range = high - low;
  const penetration = range > 0 ? ((current - low) / range) * 100 : 0;
  const clamped = Math.max(0, Math.min(100, penetration));

  let barColor = "bg-green-500";
  if (clamped > 70) barColor = "bg-red-500";
  else if (clamped >= 30) barColor = "bg-blue-500";

  return (
    <div className="flex items-center gap-2 min-w-[180px]">
      <div className="relative w-full h-2 bg-gray-800 rounded overflow-hidden">
        <div
          className={`absolute top-0 left-0 h-full rounded ${barColor}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span className="text-xs font-mono text-gray-400 w-10 text-right">
        {clamped.toFixed(0)}%
      </span>
    </div>
  );
}
```

**Step 2: Verify no other files import getSignal**

Run: `grep -r "getSignal" frontend/src/`
Expected: No results

**Step 3: Commit**

```bash
git add frontend/src/components/etf/RiskBar.tsx
git commit -m "refactor: remove unused getSignal from RiskBar"
```

---

### Task 8: Build and verify

**Step 1: Run backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests pass

**Step 2: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors

**Step 3: Commit (if any fixes needed)**

Only commit if fixes were required during verification.
