# Trading Rules — Position Sizing

## Overview

Add a Settings page with configurable trading rules. The first rule is **max position size**: a percentage threshold (default 2.5%) that prevents the dashboard from advising "Buy" on positions that are already at or above the limit. The risk range signal stays visible, but a warning is appended when the position is too large.

## Decisions

- **Position weight** = `(shares * current_price) / total_portfolio_value * 100`
- **Signal override**: Keep "Buy" (green) but append a yellow warning: `Buy ⚠ Max Size`
- **Storage**: New `trading_rules` DynamoDB table (PK: `user_id`)
- **Computation**: Frontend computes position weight and applies rules client-side
- **Navigation**: Navbar link to `/settings`

## Data Model

### DynamoDB table: `trading_rules`

| Attribute | Type | Notes |
|-----------|------|-------|
| `user_id` | String (PK) | One row per user |
| `max_position_pct` | Number | Default 2.5, range 1-100 |
| `created_at` | DateTime | Auto-set on create |
| `updated_at` | DateTime | Auto-set on create/update |

### Backend API: `/api/v1/trading-rules`

**`GET /`** — Returns user's trading rules. Creates default record (2.5%) if none exist.

Response: `{ "max_position_pct": 2.5 }`

**`PUT /`** — Updates user's trading rules.

Request: `{ "max_position_pct": 5.0 }` (validated 1-100)

Response: `{ "max_position_pct": 5.0 }`

### Pydantic schemas

- `TradingRulesResponse`: `max_position_pct: float`
- `TradingRulesUpdate`: `max_position_pct: float` (ge=1, le=100)

## Frontend

### Settings page (`/settings`)

- Dark terminal theme consistent with Dashboard
- Reuses `<Navbar />`
- Section: "Trading Rules" > "Position Sizing"
- Number input for max position % (1-100), pre-filled with current value
- Save button with inline success/error feedback

### Hook: `useTradingRules()`

- Fetches `GET /api/v1/trading-rules` on mount
- Exposes: `rules`, `loading`, `error`, `saveRules(update)`

### Navbar update

- Add "Settings" link (gear icon or text) next to Clerk UserButton
- Links to `/settings`

### Dashboard integration

- `Dashboard.tsx` calls `useTradingRules()` alongside `usePortfolio()`
- Passes `maxPositionPct` and `totalValue` down through `ETFList` → `ETFRow`
- `ETFRow` computes: `positionWeight = (shares * current_price) / totalValue * 100`
- When `positionWeight >= maxPositionPct` AND signal is "Buy":
  - Signal still shows "Buy" in green
  - Appends ` ⚠ Max Size` in yellow (`text-yellow-400`)

## Files to create/modify

### New files
- `backend/app/models/trading_rules.py` — PynamoDB model
- `backend/app/schemas/trading_rules.py` — Pydantic schemas
- `backend/app/routers/trading_rules.py` — API endpoints
- `frontend/src/pages/SettingsPage.tsx` — Settings page
- `frontend/src/hooks/useTradingRules.ts` — Data fetching hook

### Modified files
- `backend/app/main.py` — Register trading-rules router
- `frontend/src/App.tsx` — Add `/settings` route
- `frontend/src/components/layout/Navbar.tsx` — Add Settings link
- `frontend/src/components/etf/ETFList.tsx` — Pass through `maxPositionPct` and `totalValue`
- `frontend/src/components/etf/ETFRow.tsx` — Position weight check + warning display
- `frontend/src/types/index.ts` — Add `TradingRules` type
- `frontend/src/pages/Dashboard.tsx` — Call `useTradingRules()`, pass data down
