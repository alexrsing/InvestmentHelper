# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Backend: Install dependencies (using uv)
uv sync

# Backend: Run the dev server (from repo root)
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Backend: Run the dev server (from backend/ directory)
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Backend: Environment setup
cp backend/.env.example backend/.env
# Sensitive config (Clerk keys) loaded from AWS Secrets Manager

# Frontend: Install dependencies
cd frontend && npm install

# Frontend: Run dev server (port 3000, proxies /api to backend)
cd frontend && npm run dev

# Frontend: Production build
cd frontend && npm run build
```

No test framework is configured yet. No linter/formatter config exists.

## Architecture

FastAPI backend serving a REST API for ETF investment data, backed by AWS DynamoDB. React frontend with Vite, TypeScript, and Tailwind CSS.

### Request flow

```
Request → RequestLoggingMiddleware → RateLimitMiddleware → SecurityHeadersMiddleware → CORS → Router → Dependency (JWT auth) → Handler
```

All API routes are under `/api/v1` (configured via `settings.API_V1_STR`). Routers: `etfs` at `/api/v1/etfs`, `portfolio` at `/api/v1/portfolio`.

### Key layers

- **`backend/app/main.py`** — FastAPI app setup, middleware stack, global exception handler, health check at `/health`
- **`backend/app/core/config.py`** — `Settings` class using pydantic-settings; Clerk keys loaded from AWS Secrets Manager (`investment-helper/config`)
- **`backend/app/core/security.py`** — Clerk JWT validation via JWKS (RS256 via PyJWT)
- **`backend/app/core/dependencies.py`** — FastAPI dependencies for auth: `get_current_active_user` (standard auth), `require_role("admin")` (RBAC factory)
- **`backend/app/core/middleware.py`** — Three middlewares: security headers, in-memory per-IP rate limiting, request logging
- **`backend/app/models/etf.py`** — PynamoDB models: `ETF` (hash key: ticker, includes `open_price`, `risk_range_low`, `risk_range_high`) and `ETFHistory` (hash: ticker, range: date string). Tables: `etfs`, `etf_history`
- **`backend/app/models/portfolio.py`** — `Portfolio` model (hash key: user_id) with `holdings` (ListAttribute of `HoldingMap`). Table: `portfolios`
- **`backend/app/schemas/etf.py`** — Pydantic v2 schemas with field validators for input/output validation
- **`backend/app/schemas/portfolio.py`** — Portfolio response schemas (`PortfolioResponse`, `PositionResponse`)
- **`backend/app/routers/etfs.py`** — Three endpoints: `GET /` (list all), `GET /{ticker}`, `GET /{ticker}/history`
- **`backend/app/routers/portfolio.py`** — `GET /portfolio` endpoint: returns portfolio with positions enriched with live ETF data, calculates total_value and percent_change
- **`backend/app/services/`** — Stub files (`etf_service.py`, `portfolio_service.py`) with unimplemented async functions

### Patterns to follow when adding new routes

1. Create Pydantic schemas in `backend/app/schemas/`
2. Create PynamoDB models in `backend/app/models/`
3. Add router in `backend/app/routers/` with `Depends(get_current_active_user)` on all protected endpoints
4. Register router in `main.py` with `prefix=settings.API_V1_STR`
5. Use `ErrorResponse` schema in router `responses` dict for standard error codes
6. Catch exceptions in handlers — log details internally, return generic messages to clients

### DynamoDB

Uses PynamoDB ORM. Models hardcode `region = "us-east-1"` in their Meta class. Set `DYNAMODB_ENDPOINT` in `.env` for local DynamoDB during development.

### Auth

All API endpoints require JWT Bearer tokens issued by Clerk. Tokens are validated via Clerk's JWKS endpoint (RS256). Token payload carries `sub` (user_id), `email`, `username`.

### Frontend

Vite + React + TypeScript with Tailwind CSS v4, React Router v7, Recharts, and Clerk authentication. Dark terminal-style stock analysis dashboard.

- **`frontend/src/main.tsx`** — Entry point, ClerkProvider with dark theme
- **`frontend/src/App.tsx`** — BrowserRouter, routes: `/sign-in/*` (public), `/` (protected Dashboard)
- **`frontend/src/api/client.ts`** — Generic `apiFetch<T>()` wrapper with Clerk token injection via `getToken()`
- **`frontend/src/hooks/usePortfolio.ts`** — Fetches portfolio summary from `/api/v1/portfolio`
- **`frontend/src/hooks/useETFHistory.ts`** — On-demand fetch of ETF history for detail modal
- **`frontend/src/pages/SignInPage.tsx`** — Clerk pre-built `<SignIn />` component
- **`frontend/src/pages/Dashboard.tsx`** — Main dashboard: portfolio summary + ETF position list + detail modal
- **`frontend/src/components/layout/Navbar.tsx`** — App title + Clerk UserButton
- **`frontend/src/components/portfolio/PortfolioSummary.tsx`** — 3 stat cards (total value, initial value, % change)
- **`frontend/src/components/etf/ETFList.tsx`** — Vertical stack of ETF position rows
- **`frontend/src/components/etf/ETFRow.tsx`** — Single ETF row: ticker, prices, risk range, penetration bar
- **`frontend/src/components/etf/RiskBar.tsx`** — Visual risk range penetration bar (green/yellow/red)
- **`frontend/src/components/etf/ETFDetailModal.tsx`** — Modal with Recharts sparkline (close price + risk range reference lines, ISO date x-axis)
- **`frontend/src/types/index.ts`** — TypeScript interfaces (ETFPosition, PortfolioSummary, ETFHistoryItem, ETFHistoryResponse)

**Key patterns:**
- Clerk `<SignedIn>`/`<SignedOut>` components protect routes, redirect to `/sign-in`
- Clerk `useAuth().getToken()` provides JWTs for backend API calls
- ETF detail modal shows 2-10 trading days of history; displays "ETF does not have required history data" if < 2 days
- Responsive: mobile-first with Tailwind `md:` breakpoints

### Hedgeye Tracker

Parses Hedgeye risk range emails from Gmail, writes to hedgeye-specific DynamoDB tables, and updates `risk_range_low`/`risk_range_high` on the shared `etfs` table via partial updates.

- **`hedgeye-tracker/`** — Separate Python project at monorepo root (parallel to `price-fetcher/`, `backend/`)
- **`hedgeye-tracker/CLAUDE.md`** — Detailed module documentation
- **Entry points:** `lambda_handler.py` (Lambda), `src/main.py` (CLI)
- **DynamoDB tables (own):** `hedgeye_daily_ranges`, `hedgeye_weekly_ranges`
- **Shared table access:** Partial updates on `etfs` table (`risk_range_low`, `risk_range_high` fields only)
- **Gmail auth:** Service account credentials in AWS Secrets Manager (`{env}/hedgeye/gmail-service-account`)

```bash
# Install dependencies
cd hedgeye-tracker && uv sync

# Run locally
cd hedgeye-tracker/src && python main.py --skip-validation

# Run tests
cd hedgeye-tracker && python -m pytest tests/ -v
```
