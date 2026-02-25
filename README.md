# Investment Helper

A web application for tracking and managing ETF investments. FastAPI backend with a React frontend.

## Tech Stack

**Backend:**
- Python 3.12
- FastAPI + Uvicorn
- AWS DynamoDB (via PynamoDB ORM)
- JWT authentication (python-jose, passlib)
- Pydantic v2 for validation

**Frontend:**
- React 19, TypeScript
- Vite 7
- Tailwind CSS v4
- React Router v7
- Recharts

## Prerequisites

- Python 3.12+
- Node.js 22+
- AWS credentials (for DynamoDB access), or a local DynamoDB instance

## Getting Started

### 1. Backend setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
cp backend/.env.example backend/.env
# Edit backend/.env — at minimum, set SECRET_KEY (e.g. output of `openssl rand -hex 32`)
```

For local development without AWS, uncomment `DYNAMODB_ENDPOINT` in `backend/.env` and point it at a local DynamoDB instance.

### 2. Run the backend

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`. Health check: `GET /health`.

### 3. Frontend setup

```bash
cd frontend
npm install
```

### 4. Run the frontend

```bash
cd frontend
npm run dev
```

The frontend runs at `http://localhost:3000` and proxies `/api` requests to the backend.

## Docker

Build and run the full stack in a single container:

```bash
docker build -t investment-helper .
docker run -p 8000:8000 investment-helper
```

## API

All routes are under `/api/v1`. Authentication is required (JWT Bearer token).

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/etfs/{ticker}` | Get ETF details by ticker |
| `GET` | `/api/v1/etfs/{ticker}/history` | Get ETF price history (supports date range filtering) |
| `GET` | `/health` | Health check (no auth required) |

## Project Structure

```
backend/
  app/
    main.py          # App setup, middleware, health check
    core/
      config.py      # Settings (pydantic-settings, loads .env)
      security.py    # JWT creation/decoding, password hashing
      dependencies.py # Auth dependencies for route protection
      middleware.py   # Security headers, rate limiting, request logging
    models/          # PynamoDB DynamoDB models
    schemas/         # Pydantic request/response schemas
    routers/         # API route handlers
    services/        # Business logic (stubs)
frontend/
  src/
    api/             # API client and endpoint functions
    components/      # UI components (layout, common, portfolio, trading)
    context/         # Auth context (JWT state management)
    hooks/           # Data fetching hooks with mock fallback
    mocks/           # Mock data for offline development
    pages/           # Route pages (Portfolio, Trading, Login)
```
