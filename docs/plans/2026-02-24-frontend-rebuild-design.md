# Frontend Rebuild Design

## Overview

Rebuild the frontend for InvestmentHelper as a dark terminal-style stock analysis dashboard using Vite + React + TypeScript + Tailwind CSS with Clerk authentication.

## Tech Stack

- Vite + React + TypeScript + Tailwind CSS v4
- @clerk/clerk-react for authentication (pre-built SignIn component)
- Recharts for sparkline charts
- React Router v7 for routing

## Routing

- `/sign-in` — Clerk `<SignIn />` pre-built component (public)
- `/` — Dashboard (protected, redirects to `/sign-in` if unauthenticated)

## Authentication

- `<ClerkProvider>` wraps the app with publishable key from env
- `<SignedIn>` / `<SignedOut>` components handle route protection
- `useAuth().getToken()` provides JWTs for backend API calls
- Backend already validates Clerk JWTs via JWKS (RS256)

## Dashboard Layout

### Portfolio Summary (top)

Three stat cards: total value, initial value, percentage change. Green if positive, red if negative.

### ETF Positions (vertical stack)

Each row displays:
- Ticker
- Current price
- Open price
- Risk range low and high
- Risk range penetration: horizontal visual bar with marker + percentage text

### ETF Detail Modal (on row click)

- Modal overlay with sparkline chart (Recharts)
- Lines: current price (solid), risk range low (dashed), risk range high (dashed)
- X-axis: ISO date labels from history data (e.g. `2026-02-14`)
- Period: 2-10 trading days
- If < 2 data points: show "ETF does not have required history data"

## Visual Style

- Dark terminal aesthetic
- Background: #0d1117
- Green/red accents for positive/negative values
- Monospace font for data
- Subtle borders, minimal decoration

## File Structure

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   └── client.ts
│   ├── hooks/
│   │   ├── usePortfolio.ts
│   │   ├── useETFPositions.ts
│   │   └── useETFHistory.ts
│   ├── pages/
│   │   ├── SignInPage.tsx
│   │   └── Dashboard.tsx
│   ├── components/
│   │   ├── layout/
│   │   │   └── Navbar.tsx
│   │   ├── portfolio/
│   │   │   └── PortfolioSummary.tsx
│   │   └── etf/
│   │       ├── ETFList.tsx
│   │       ├── ETFRow.tsx
│   │       ├── RiskBar.tsx
│   │       └── ETFDetailModal.tsx
│   └── types/
│       └── index.ts
```

## Data Flow

1. User visits `/` -> Clerk checks auth -> redirects to `/sign-in` if unauthenticated
2. After sign-in, Clerk redirects to `/`
3. Dashboard mounts -> `usePortfolio` calls `GET /api/v1/portfolio` -> displays summary
4. Dashboard mounts -> `useETFPositions` calls `GET /api/v1/etfs` -> renders ETF rows
5. User clicks ETF row -> modal opens -> `useETFHistory` calls `GET /api/v1/etfs/{ticker}/history` -> renders sparkline
6. If history < 2 data points -> show insufficient data message

## Backend Dependencies

The frontend assumes these backend endpoints exist (some need to be created):
- `GET /api/v1/portfolio` (new — returns total_value, initial_value, percent_change, positions)
- `GET /api/v1/etfs` (new — returns list of all ETFs with current data including risk range fields)
- `GET /api/v1/etfs/{ticker}/history` (exists — returns historical price data)

The ETF model needs new fields: `risk_range_low`, `risk_range_high` (stored in DynamoDB).

## Risk Range Penetration Calculation

```
penetration = (current_price - risk_range_low) / (risk_range_high - risk_range_low) * 100
```

Clamped to 0-100%. Displayed as a visual bar with marker position + percentage text.
