# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Backend: Install dependencies
pip install -r requirements.txt

# Backend: Run the dev server (from repo root)
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Backend: Run the dev server (from backend/ directory)
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Backend: Docker build and run
docker build -t investment-helper .
docker run -p 8000:8000 investment-helper

# Backend: Environment setup
cp backend/.env.example backend/.env
# Then edit backend/.env — SECRET_KEY is required

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

All API routes are under `/api/v1` (configured via `settings.API_V1_STR`). The only router currently is `etfs` at `/api/v1/etfs`.

### Key layers

- **`backend/app/main.py`** — FastAPI app setup, middleware stack, global exception handler, health check at `/health`
- **`backend/app/core/config.py`** — `Settings` class using pydantic-settings; loads from `backend/.env`. `SECRET_KEY` has no default and must be set.
- **`backend/app/core/security.py`** — JWT token creation/decoding (HS256 via python-jose), bcrypt password hashing via passlib
- **`backend/app/core/dependencies.py`** — FastAPI dependencies for auth: `get_current_active_user` (standard auth), `require_role("admin")` (RBAC factory)
- **`backend/app/core/middleware.py`** — Three middlewares: security headers, in-memory per-IP rate limiting, request logging
- **`backend/app/models/etf.py`** — PynamoDB models: `ETF` (hash key: ticker) and `ETFHistory` (hash: ticker, range: date string). Tables: `etfs`, `etf_history`
- **`backend/app/schemas/etf.py`** — Pydantic v2 schemas with field validators for input/output validation
- **`backend/app/routers/etfs.py`** — Two endpoints: `GET /{ticker}` and `GET /{ticker}/history` (with date range filtering)
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

All ETF endpoints require JWT Bearer tokens. Tokens carry `sub` (user_id), `email`, `username` in payload. There is no login/registration endpoint yet — tokens must be created programmatically via `create_access_token()` for testing.

### Frontend

Vite + React + TypeScript with Tailwind CSS v4, React Router v7, and Recharts.

- **`frontend/src/main.tsx`** — Entry point, renders `<App />`
- **`frontend/src/App.tsx`** — BrowserRouter, AuthProvider, route definitions
- **`frontend/src/context/AuthContext.tsx`** — JWT auth state, token decode/expiry, login/logout methods
- **`frontend/src/api/client.ts`** — Fetch wrapper with Bearer token injection
- **`frontend/src/api/etfApi.ts`** — ETF endpoint calls (`getETF`, `getETFHistory`)
- **`frontend/src/hooks/`** — `useETF`, `useETFHistory` (real API with mock fallback), `usePortfolio` (mock data)
- **`frontend/src/pages/`** — `PortfolioOverview` (`/`), `Trading` (`/trading`), `Login` (`/login`)
- **`frontend/src/components/`** — Organized by feature: `layout/`, `common/`, `portfolio/`, `trading/`
- **`frontend/src/mocks/`** — Mock data for portfolio and ETFs (used when backend is unavailable)

**Key patterns:**
- `ProtectedRoute` wraps authenticated routes, redirects to `/login`
- Trading page calls real backend, falls back to mock data if API unreachable
- Responsive: mobile-first with Tailwind `md:`/`lg:` breakpoints, hamburger menu on mobile
