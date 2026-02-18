# Frontend-Backend Integration

This document lists every endpoint the frontend expects from the backend, the exact JSON shape required, and example Python code showing how the backend satisfies each one.

---

## Authentication

All API requests (except `/health`) require a JWT Bearer token in the `Authorization` header. The frontend reads the token from `localStorage` and attaches it automatically via `frontend/src/api/client.ts`.

**Header format:**
```
Authorization: Bearer <jwt_token>
```

**Required JWT payload fields** (read by `frontend/src/context/AuthContext.tsx`):

| Field      | Type   | Description                        |
|------------|--------|------------------------------------|
| `sub`      | string | User ID (mapped to `user_id`)      |
| `email`    | string | User email                         |
| `username` | string | Display name                       |
| `exp`      | number | Expiry timestamp (Unix epoch secs) |
| `type`     | string | Must be `"access"`                 |

**Example: Generate a dev token**

```python
# Run from the backend/ directory with SECRET_KEY set in .env
from datetime import timedelta
from app.core.security import create_access_token

token = create_access_token(
    data={
        "sub": "user_001",
        "email": "dev@example.com",
        "username": "dev",
    },
    expires_delta=timedelta(hours=24),
)
print(token)
```

---

## Endpoint 1 — Get ETF Data

| Property   | Value                                   |
|------------|-----------------------------------------|
| Method     | `GET`                                   |
| Path       | `/api/v1/etfs/{ticker}`                 |
| Auth       | Bearer token required                   |
| Frontend   | `frontend/src/api/etfApi.ts → getETF()` |
| Hook       | `frontend/src/hooks/useETF.ts`          |
| Used on    | Trading page (`/trading`)               |

### Request

```
GET /api/v1/etfs/SPY HTTP/1.1
Authorization: Bearer <token>
```

`ticker` is a path parameter — 1-10 letters, case-insensitive (backend uppercases it).

### Expected JSON Response

```json
{
  "ticker": "SPY",
  "name": "SPDR S&P 500 ETF Trust",
  "description": "Tracks the S&P 500 index.",
  "expense_ratio": 0.0945,
  "aum": 560000000000,
  "inception_date": "1993-01-22T00:00:00Z",
  "current_price": 587.42,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2026-02-18T00:00:00Z"
}
```

### Frontend TypeScript type (`frontend/src/types/etf.ts`)

```typescript
interface ETFResponse {
  ticker: string;
  name: string | null;
  description: string | null;
  expense_ratio: number | null;
  aum: number | null;
  inception_date: string | null;
  current_price: number | null;
  created_at: string;
  updated_at: string;
}
```

### Backend Pydantic schema (`backend/app/schemas/etf.py`)

```python
class ETFResponse(ETFBase):
    name: Optional[str] = None
    description: Optional[str] = None
    expense_ratio: Optional[float] = Field(None, ge=0, le=100)
    aum: Optional[float] = Field(None, ge=0)
    inception_date: Optional[datetime] = None
    current_price: Optional[float] = Field(None, gt=0)
    created_at: datetime
    updated_at: datetime
```

### Example: Seed DynamoDB and serve the response

```python
from datetime import datetime, timezone
from app.models.etf import ETF

# Create or update an ETF record in DynamoDB
etf = ETF(
    ticker="SPY",
    name="SPDR S&P 500 ETF Trust",
    description="Tracks the S&P 500 index.",
    expense_ratio=0.0945,
    aum=560_000_000_000,
    inception_date=datetime(1993, 1, 22, tzinfo=timezone.utc),
    current_price=587.42,
    created_at=datetime.now(timezone.utc),
    updated_at=datetime.now(timezone.utc),
)
etf.save()
```

The existing router at `backend/app/routers/etfs.py` handles the lookup:

```python
@router.get("/{ticker}", response_model=ETFResponse)
async def get_etf(ticker: str, current_user: dict = Depends(get_current_active_user)):
    ticker = ticker.upper()
    etf = ETF.get(ticker)  # PynamoDB lookup by hash key
    return ETFResponse(
        ticker=etf.ticker,
        name=etf.name,
        description=etf.description,
        expense_ratio=etf.expense_ratio,
        aum=etf.aum,
        inception_date=etf.inception_date,
        current_price=etf.current_price,
        created_at=etf.created_at,
        updated_at=etf.updated_at,
    )
```

---

## Endpoint 2 — Get ETF Price History

| Property   | Value                                            |
|------------|--------------------------------------------------|
| Method     | `GET`                                            |
| Path       | `/api/v1/etfs/{ticker}/history`                  |
| Auth       | Bearer token required                            |
| Frontend   | `frontend/src/api/etfApi.ts → getETFHistory()`   |
| Hook       | `frontend/src/hooks/useETFHistory.ts`            |
| Used on    | Trading page (`/trading`) — Risk Range Sparkline + Price History Table |

### Request

```
GET /api/v1/etfs/SPY/history?limit=200 HTTP/1.1
Authorization: Bearer <token>
```

### Query Parameters

| Param        | Type   | Default | Description                  |
|--------------|--------|---------|------------------------------|
| `start_date` | string | `null`  | `YYYY-MM-DD` format          |
| `end_date`   | string | `null`  | `YYYY-MM-DD` format          |
| `limit`      | int    | `100`   | 1–1000, max records returned |

The frontend sends `limit=200` by default (see `useETFHistory.ts:17`).

### Expected JSON Response

```json
{
  "ticker": "SPY",
  "history": [
    {
      "date": "2026-02-14",
      "open_price": 585.10,
      "high_price": 589.75,
      "low_price": 583.20,
      "close_price": 587.42,
      "adjusted_close": 587.42,
      "volume": 45230000
    },
    {
      "date": "2026-02-13",
      "open_price": 582.30,
      "high_price": 586.90,
      "low_price": 580.15,
      "close_price": 585.10,
      "adjusted_close": 585.10,
      "volume": 38750000
    }
  ],
  "total_records": 2
}
```

### Frontend TypeScript types (`frontend/src/types/etf.ts`)

```typescript
interface ETFHistoryItem {
  date: string;           // "YYYY-MM-DD"
  open_price: number;
  high_price: number;     // Used for risk range high line
  low_price: number;      // Used for risk range low line
  close_price: number;    // Used for risk range close line
  adjusted_close: number | null;
  volume: number;
}

interface ETFHistoryResponse {
  ticker: string;
  history: ETFHistoryItem[];
  total_records: number;
}
```

### How the frontend uses this data

The `RiskRangeSparkline` component (`frontend/src/components/trading/RiskRangeSparkline.tsx`) renders when `history.length >= 2` and uses three fields per data point:

- **`high_price`** — dashed red line (top of risk channel)
- **`low_price`** — dashed green line (bottom of risk channel)
- **`close_price`** — solid blue line (actual price within the channel)

The area between high and low is shaded to visualize the risk range. The `PriceHistoryTable` component shows all fields in a table (most recent 30 records).

### Example: Seed history records in DynamoDB

```python
from datetime import datetime, timezone
from app.models.etf import ETFHistory

# Each record needs ticker (hash key) + date (range key)
records = [
    {
        "ticker": "SPY",
        "date": "2026-02-14",
        "open_price": 585.10,
        "high_price": 589.75,
        "low_price": 583.20,
        "close_price": 587.42,
        "adjusted_close": 587.42,
        "volume": 45230000,
    },
    {
        "ticker": "SPY",
        "date": "2026-02-13",
        "open_price": 582.30,
        "high_price": 586.90,
        "low_price": 580.15,
        "close_price": 585.10,
        "adjusted_close": 585.10,
        "volume": 38750000,
    },
]

for rec in records:
    item = ETFHistory(
        ticker=rec["ticker"],
        date=rec["date"],
        open_price=rec["open_price"],
        high_price=rec["high_price"],
        low_price=rec["low_price"],
        close_price=rec["close_price"],
        adjusted_close=rec["adjusted_close"],
        volume=rec["volume"],
        created_at=datetime.now(timezone.utc),
    )
    item.save()
```

---

## Error Responses

All endpoints return errors in this shape, which the frontend handles in `api/client.ts`:

```json
{
  "detail": "ETF with ticker 'XYZ' not found",
  "error_code": "NOT_FOUND"
}
```

| Status | Meaning                | Frontend behavior               |
|--------|------------------------|---------------------------------|
| 401    | Invalid/expired token  | Caught by hook, falls back to mock data. `AuthContext` clears expired tokens on page load. |
| 404    | ETF not found          | Caught by hook, shows error if no mock data exists for that ticker. |
| 422    | Validation error       | Prevented by frontend ticker validation (`^[A-Za-z]{1,10}$`) before the request is sent. |
| 429    | Rate limited           | Caught by hook, falls back to mock data. |
| 500    | Server error           | Caught by hook, falls back to mock data. |

---

## Mock Data Fallback

Both `useETF` and `useETFHistory` hooks wrap their API calls in try/catch. If the backend is unreachable or returns an error, they fall back to mock data from `frontend/src/mocks/etfData.ts`. Mock tickers available: **SPY**, **QQQ**, **VOO**.

The portfolio page (`/`) uses only mock data since `backend/app/services/portfolio_service.py` is a stub with no implemented endpoints.

---

## Endpoints Not Yet Implemented

These are referenced in the frontend architecture but have no backend route yet:

| Feature             | Frontend status             | Backend status                |
|---------------------|-----------------------------|-------------------------------|
| Login (`POST`)      | Login page has token paste field; calls `AuthContext.login(token)` | No login/register endpoint. Tokens created via `create_access_token()`. |
| Portfolio data      | `usePortfolio` hook returns mock data | `portfolio_service.py` is a stub. |

When these backend endpoints are built, the frontend hooks just need their API calls swapped in — the components and routing are already wired up.
