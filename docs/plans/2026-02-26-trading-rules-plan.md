# Trading Rules — Position Sizing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Settings page with configurable max position size trading rule that warns users when a position is too large to buy more.

**Architecture:** Frontend-computed approach. Backend provides a simple CRUD API for persisting trading rules in DynamoDB. Frontend fetches rules, computes position weights from existing portfolio data, and displays warnings alongside existing risk range signals.

**Tech Stack:** FastAPI + PynamoDB (backend), React + TypeScript + Tailwind CSS (frontend), DynamoDB (storage)

---

### Task 1: Backend — PynamoDB model for trading rules

**Files:**
- Create: `backend/app/models/trading_rules.py`

**Step 1: Create the model file**

```python
from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute,
    NumberAttribute,
    UTCDateTimeAttribute,
)
from datetime import datetime, timezone


class TradingRules(Model):
    class Meta:
        table_name = "trading_rules"
        region = "us-east-1"

    user_id = UnicodeAttribute(hash_key=True)
    max_position_pct = NumberAttribute(default=2.5)
    created_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
    updated_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
```

**Step 2: Verify syntax**

Run: `cd /home/alex/InvestmentHelper && python3 -m py_compile backend/app/models/trading_rules.py`
Expected: No output (clean compile)

**Step 3: Commit**

```bash
git add backend/app/models/trading_rules.py
git commit -m "feat: add TradingRules PynamoDB model"
```

---

### Task 2: Backend — Pydantic schemas for trading rules

**Files:**
- Create: `backend/app/schemas/trading_rules.py`

**Step 1: Create the schemas file**

```python
from pydantic import BaseModel, Field


class TradingRulesResponse(BaseModel):
    max_position_pct: float


class TradingRulesUpdate(BaseModel):
    max_position_pct: float = Field(..., ge=1, le=100)
```

**Step 2: Verify syntax**

Run: `cd /home/alex/InvestmentHelper && python3 -m py_compile backend/app/schemas/trading_rules.py`
Expected: No output (clean compile)

**Step 3: Commit**

```bash
git add backend/app/schemas/trading_rules.py
git commit -m "feat: add TradingRules Pydantic schemas"
```

---

### Task 3: Backend — Trading rules router

**Files:**
- Create: `backend/app/routers/trading_rules.py`

**Step 1: Create the router**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pynamodb.exceptions import DoesNotExist
from datetime import datetime, timezone

from app.core.dependencies import get_current_active_user
from app.models.trading_rules import TradingRules
from app.schemas.trading_rules import TradingRulesResponse, TradingRulesUpdate
from app.schemas.etf import ErrorResponse

router = APIRouter(
    prefix="/trading-rules",
    tags=["Trading Rules"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


@router.get("", response_model=TradingRulesResponse)
async def get_trading_rules(current_user: dict = Depends(get_current_active_user)):
    user_id = current_user["user_id"]

    try:
        rules = TradingRules.get(user_id)
        return TradingRulesResponse(max_position_pct=float(rules.max_position_pct))
    except DoesNotExist:
        # Create default rules for new users
        rules = TradingRules(user_id=user_id, max_position_pct=2.5)
        rules.save()
        return TradingRulesResponse(max_position_pct=2.5)
    except Exception as e:
        print(f"Error fetching trading rules for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching trading rules",
        )


@router.put("", response_model=TradingRulesResponse)
async def update_trading_rules(
    update: TradingRulesUpdate,
    current_user: dict = Depends(get_current_active_user),
):
    user_id = current_user["user_id"]

    try:
        try:
            rules = TradingRules.get(user_id)
            rules.max_position_pct = update.max_position_pct
            rules.updated_at = datetime.now(timezone.utc)
            rules.save()
        except DoesNotExist:
            rules = TradingRules(
                user_id=user_id,
                max_position_pct=update.max_position_pct,
            )
            rules.save()

        return TradingRulesResponse(max_position_pct=update.max_position_pct)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating trading rules for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating trading rules",
        )
```

**Step 2: Verify syntax**

Run: `cd /home/alex/InvestmentHelper && python3 -m py_compile backend/app/routers/trading_rules.py`
Expected: No output (clean compile)

**Step 3: Commit**

```bash
git add backend/app/routers/trading_rules.py
git commit -m "feat: add trading rules API endpoints (GET/PUT)"
```

---

### Task 4: Backend — Register router in main.py

**Files:**
- Modify: `backend/app/main.py:12` (add import) and `main.py:49-52` (add router registration)

**Step 1: Add import**

At line 12, after `from app.routers import portfolio`, add:
```python
from app.routers import trading_rules
```

**Step 2: Register router**

After the portfolio router registration (line 52), add:
```python
app.include_router(
    trading_rules.router,
    prefix=settings.API_V1_STR,
)
```

**Step 3: Verify syntax**

Run: `cd /home/alex/InvestmentHelper && python3 -m py_compile backend/app/main.py`
Expected: No output (clean compile)

**Step 4: Verify server starts**

Run: `cd /home/alex/InvestmentHelper/backend && uvicorn app.main:app --host 0.0.0.0 --port 8000` (briefly, then ctrl-c)
Expected: "Uvicorn running on http://0.0.0.0:8000"

**Step 5: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: register trading-rules router"
```

---

### Task 5: Frontend — TypeScript types and API hook

**Files:**
- Modify: `frontend/src/types/index.ts` (add TradingRules type)
- Create: `frontend/src/hooks/useTradingRules.ts`

**Step 1: Add TypeScript type**

At the end of `frontend/src/types/index.ts`, add:
```typescript
export interface TradingRules {
  max_position_pct: number;
}
```

**Step 2: Create the hook**

```typescript
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@clerk/clerk-react";
import { apiFetch } from "../api/client";
import type { TradingRules } from "../types";

export function useTradingRules() {
  const { getToken } = useAuth();
  const [rules, setRules] = useState<TradingRules | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRules = useCallback(() => {
    setLoading(true);
    setError(null);
    apiFetch<TradingRules>("/api/v1/trading-rules", getToken)
      .then(setRules)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [getToken]);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const saveRules = useCallback(
    async (update: Partial<TradingRules>) => {
      const res = await apiFetch<TradingRules>(
        "/api/v1/trading-rules",
        getToken,
        {
          method: "PUT",
          body: JSON.stringify(update),
        }
      );
      setRules(res);
      return res;
    },
    [getToken]
  );

  return { rules, loading, error, saveRules, refetch: fetchRules };
}
```

**Step 3: Verify build**

Run: `cd /home/alex/InvestmentHelper/frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/hooks/useTradingRules.ts
git commit -m "feat: add TradingRules type and useTradingRules hook"
```

---

### Task 6: Frontend — Settings page

**Files:**
- Create: `frontend/src/pages/SettingsPage.tsx`

**Step 1: Create the Settings page**

```tsx
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import Navbar from "../components/layout/Navbar";
import { useTradingRules } from "../hooks/useTradingRules";

export default function SettingsPage() {
  const { rules, loading, error, saveRules } = useTradingRules();
  const [maxPct, setMaxPct] = useState("");
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  useEffect(() => {
    if (rules) {
      setMaxPct(String(rules.max_position_pct));
    }
  }, [rules]);

  const handleSave = async () => {
    const value = parseFloat(maxPct);
    if (isNaN(value) || value < 1 || value > 100) {
      setFeedback({ type: "error", message: "Enter a value between 1 and 100" });
      return;
    }

    setSaving(true);
    setFeedback(null);
    try {
      await saveRules({ max_position_pct: value });
      setFeedback({ type: "success", message: "Saved" });
    } catch (e) {
      setFeedback({
        type: "error",
        message: e instanceof Error ? e.message : "Failed to save",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-100">
      <Navbar />

      <main className="max-w-6xl mx-auto px-4 py-6">
        <div className="flex items-center gap-3 mb-6">
          <Link
            to="/"
            className="text-gray-500 hover:text-gray-300 transition-colors text-sm font-mono"
          >
            &larr; Dashboard
          </Link>
          <h1 className="text-sm text-gray-500 uppercase tracking-wider font-mono">
            Settings
          </h1>
        </div>

        {loading && (
          <div className="text-gray-500 font-mono text-center py-12">
            Loading settings...
          </div>
        )}

        {error && (
          <div className="text-red-400 font-mono text-center py-12">{error}</div>
        )}

        {rules && (
          <div className="border border-gray-800 rounded bg-[#161b22] p-6">
            <h2 className="text-green-400 font-mono font-bold text-sm uppercase tracking-wider mb-4">
              Trading Rules
            </h2>

            <div className="border-t border-gray-800 pt-4">
              <h3 className="text-gray-300 font-mono text-sm mb-1">
                Position Sizing
              </h3>
              <p className="text-gray-500 text-xs mb-4">
                Maximum percentage of total portfolio value for a single position.
                When a position reaches this limit, a warning is shown instead of a
                buy signal.
              </p>

              <div className="flex items-center gap-3">
                <label
                  htmlFor="max-position-pct"
                  className="text-xs text-gray-500 uppercase font-mono"
                >
                  Max Position
                </label>
                <div className="flex items-center gap-1">
                  <input
                    id="max-position-pct"
                    type="number"
                    min={1}
                    max={100}
                    step={0.5}
                    value={maxPct}
                    onChange={(e) => {
                      setMaxPct(e.target.value);
                      setFeedback(null);
                    }}
                    className="w-20 px-2 py-1.5 bg-[#0d1117] border border-gray-700 rounded text-gray-100 font-mono text-sm focus:border-green-400 focus:outline-none"
                  />
                  <span className="text-gray-500 font-mono text-sm">%</span>
                </div>
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="px-3 py-1.5 border border-gray-700 rounded text-xs font-mono text-gray-300 hover:text-green-400 hover:border-green-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {saving ? "SAVING..." : "SAVE"}
                </button>
                {feedback && (
                  <span
                    className={`text-xs font-mono ${
                      feedback.type === "success"
                        ? "text-green-400"
                        : "text-red-400"
                    }`}
                  >
                    {feedback.message}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
```

**Step 2: Verify build**

Run: `cd /home/alex/InvestmentHelper/frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat: add Settings page with position sizing rule"
```

---

### Task 7: Frontend — Add Settings route and Navbar link

**Files:**
- Modify: `frontend/src/App.tsx:7-8` (add import) and `App.tsx:14-27` (add route)
- Modify: `frontend/src/components/layout/Navbar.tsx` (add Settings link)

**Step 1: Update App.tsx**

Add import at line 8, after the Dashboard import:
```typescript
import SettingsPage from "./pages/SettingsPage";
```

Add a new route after the Dashboard route (before the catch-all). Insert between line 27 (`/>`) and line 28 (`<Route path="*"`):
```tsx
        <Route
          path="/settings"
          element={
            <>
              <SignedIn>
                <SettingsPage />
              </SignedIn>
              <SignedOut>
                <RedirectToSignIn />
              </SignedOut>
            </>
          }
        />
```

**Step 2: Update Navbar.tsx**

Replace the entire Navbar component to add a Settings link. The updated component adds a `Link` import and a gear-icon settings link next to the UserButton:

```tsx
import { UserButton } from "@clerk/clerk-react";
import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <nav className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-[#0d1117]">
      <div className="flex items-center gap-2">
        <Link to="/" className="text-green-400 font-mono font-bold text-lg tracking-wider hover:text-green-300 transition-colors">
          INVESTMENT HELPER
        </Link>
      </div>
      <div className="flex items-center gap-4">
        <Link
          to="/settings"
          className="text-gray-500 hover:text-gray-300 transition-colors text-sm font-mono"
        >
          Settings
        </Link>
        <UserButton
          appearance={{
            elements: { avatarBox: "w-8 h-8" },
          }}
        />
      </div>
    </nav>
  );
}
```

**Step 3: Verify build**

Run: `cd /home/alex/InvestmentHelper/frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/layout/Navbar.tsx
git commit -m "feat: add Settings route and navbar link"
```

---

### Task 8: Frontend — Wire trading rules into Dashboard and ETFRow

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx` (fetch rules, pass data down)
- Modify: `frontend/src/components/etf/ETFList.tsx` (pass through props)
- Modify: `frontend/src/components/etf/ETFRow.tsx` (compute position weight, show warning)

**Step 1: Update Dashboard.tsx**

Add import for `useTradingRules` at line 7 (after the `useETFHistory` import):
```typescript
import { useTradingRules } from "../hooks/useTradingRules";
```

Inside the `Dashboard` component, after the `useETFHistory` call (line 19), add:
```typescript
  const { rules: tradingRules } = useTradingRules();
```

Update the `ETFList` usage (around line 108-111) to pass the new props:
```tsx
            <ETFList
              positions={portfolio.positions}
              onSelectETF={handleSelectETF}
              totalValue={portfolio.total_value}
              maxPositionPct={tradingRules?.max_position_pct ?? null}
            />
```

**Step 2: Update ETFList.tsx**

Update the Props interface and pass through to ETFRow:

```tsx
import type { ETFPosition } from "../../types";
import ETFRow from "./ETFRow";

interface Props {
  positions: ETFPosition[];
  onSelectETF: (ticker: string) => void;
  totalValue: number;
  maxPositionPct: number | null;
}

export default function ETFList({ positions, onSelectETF, totalValue, maxPositionPct }: Props) {
  if (positions.length === 0) {
    return (
      <div className="text-gray-500 font-mono text-center py-8">
        No positions found
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {positions.map((pos) => (
        <ETFRow
          key={pos.ticker}
          position={pos}
          onClick={onSelectETF}
          totalValue={totalValue}
          maxPositionPct={maxPositionPct}
        />
      ))}
    </div>
  );
}
```

**Step 3: Update ETFRow.tsx**

Update the Props interface to accept `totalValue` and `maxPositionPct`:

```typescript
interface Props {
  position: ETFPosition;
  onClick: (ticker: string) => void;
  totalValue: number;
  maxPositionPct: number | null;
}
```

Update the component signature:
```typescript
export default function ETFRow({ position, onClick, totalValue, maxPositionPct }: Props) {
```

After the existing `priceChange`/`changeColor` block (around line 28-29), add the position weight check:
```typescript
  const positionWeight =
    current_price != null && totalValue > 0
      ? (position.shares * current_price) / totalValue * 100
      : null;

  const isMaxSize =
    positionWeight != null &&
    maxPositionPct != null &&
    positionWeight >= maxPositionPct;
```

In the signal display section (the IIFE inside the "Penetration" label area), after the signal `<span>`, add the max size warning. Replace the existing signal IIFE block with:

```tsx
          {risk_range_low != null &&
            risk_range_high != null &&
            current_price != null &&
            risk_range_high - risk_range_low > 0 && (() => {
              const pen = Math.max(0, Math.min(100,
                ((current_price - risk_range_low) / (risk_range_high - risk_range_low)) * 100
              ));
              const signal = getSignal(pen);
              return (
                <>
                  <span className={`${signal.color} font-bold`}>
                    {" \u00b7 "}{signal.label}
                  </span>
                  {isMaxSize && signal.label === "Buy" && (
                    <span className="text-yellow-400 font-bold">
                      {" \u26a0 Max Size"}
                    </span>
                  )}
                </>
              );
            })()}
```

**Step 4: Verify build**

Run: `cd /home/alex/InvestmentHelper/frontend && npm run build`
Expected: Build succeeds

**Step 5: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx frontend/src/components/etf/ETFList.tsx frontend/src/components/etf/ETFRow.tsx
git commit -m "feat: display max size warning on positions exceeding trading rule"
```

---

### Task 9: Create DynamoDB table

**Step 1: Create the `trading_rules` table in DynamoDB**

Run: `aws dynamodb create-table --table-name trading_rules --attribute-definitions AttributeName=user_id,AttributeType=S --key-schema AttributeName=user_id,KeyType=HASH --billing-mode PAY_PER_REQUEST --region us-east-1`

Expected: Table creation confirmation JSON

**Step 2: Commit** (nothing to commit — infrastructure only)

---

### Task 10: End-to-end verification

**Step 1: Start backend**

Run: `cd /home/alex/InvestmentHelper/backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

**Step 2: Start frontend**

Run: `cd /home/alex/InvestmentHelper/frontend && npm run dev`

**Step 3: Manual verification checklist**

1. Navigate to `http://localhost:3000` — Dashboard loads normally
2. Navbar shows "Settings" link next to user avatar
3. Click "Settings" — Settings page loads with position sizing rule
4. Default value is 2.5%
5. Change value to 5%, click Save — "Saved" feedback appears
6. Refresh page — value persists as 5%
7. Navigate back to Dashboard
8. ETF positions with penetration < 30% AND position weight >= 5% show: `Penetration · Buy ⚠ Max Size`
9. ETF positions with penetration < 30% AND position weight < 5% show: `Penetration · Buy` (no warning)
10. ETF positions with penetration >= 30% show normal Stay/Sell signals (no warning regardless of size)
