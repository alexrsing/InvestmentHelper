# Agentic Trading Recommendations Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add on-demand LLM-powered ETF research to the trading dashboard, using Gemini 2.0 Flash with Google Search grounding behind a provider-agnostic interface.

**Architecture:** A "Search for data" button triggers `POST /api/v1/portfolio/research`, which runs parallel per-ticker Gemini calls for Buy/Sell positions only. Results are cached in a new `etf_research` DynamoDB table with 24h auto-expiry and served inline on the dashboard with sentiment badges.

**Tech Stack:** google-genai SDK, FastAPI, PynamoDB, React/TypeScript, asyncio

---

### Task 1: Add google-genai dependency and config settings

**Files:**
- Modify: `pyproject.toml:7-15`
- Modify: `backend/app/core/config.py:17-46`

**Step 1: Add google-genai to pyproject.toml**

In `pyproject.toml`, add `"google-genai"` to the dependencies list:

```toml
dependencies = [
    "fastapi",
    "uvicorn",
    "boto3",
    "pynamodb",
    "PyJWT[crypto]",
    "python-multipart",
    "pydantic-settings",
    "google-genai",
]
```

**Step 2: Install dependencies**

Run: `cd /home/alex/InvestmentHelper && uv sync`

**Step 3: Add research config to Settings**

In `backend/app/core/config.py`, add these fields to the `Settings` class after the `DYNAMODB_ENDPOINT` line:

```python
    # Research
    RESEARCH_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = _secrets.get("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-2.0-flash"
    RESEARCH_EXPIRY_HOURS: int = 24
```

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock backend/app/core/config.py
git commit -m "chore: add google-genai dependency and research config"
```

---

### Task 2: Create ETFResearch DynamoDB model

**Files:**
- Create: `backend/app/models/etf_research.py`

**Step 1: Create the model**

Create `backend/app/models/etf_research.py`:

```python
from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, UTCDateTimeAttribute
from datetime import datetime, timezone


class ETFResearch(Model):
    class Meta:
        table_name = "etf_research"
        region = "us-east-1"

    user_id = UnicodeAttribute(hash_key=True)
    ticker = UnicodeAttribute(range_key=True)
    sentiment = UnicodeAttribute()  # "Bullish", "Bearish", "Neutral"
    summary = UnicodeAttribute()
    signal_at_research = UnicodeAttribute()  # "Buy" or "Sell"
    researched_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
```

**Step 2: Commit**

```bash
git add backend/app/models/etf_research.py
git commit -m "feat: add ETFResearch DynamoDB model"
```

---

### Task 3: Create provider abstraction

**Files:**
- Create: `backend/app/services/research/__init__.py`
- Create: `backend/app/services/research/provider.py`

**Step 1: Create the research services directory**

Run: `mkdir -p backend/app/services/research`

**Step 2: Create empty `__init__.py`**

Create `backend/app/services/research/__init__.py` as an empty file.

**Step 3: Create provider interface and result dataclass**

Create `backend/app/services/research/provider.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ResearchResult:
    sentiment: str  # "Bullish", "Bearish", "Neutral"
    summary: str


class ResearchProvider(ABC):
    @abstractmethod
    async def research_ticker(
        self,
        ticker: str,
        name: str,
        signal: str,
        current_price: float,
        risk_range_low: float,
        risk_range_high: float,
    ) -> ResearchResult:
        """Research a single ETF ticker and return sentiment + summary."""
```

**Step 4: Commit**

```bash
git add backend/app/services/research/
git commit -m "feat: add ResearchProvider abstract interface"
```

---

### Task 4: Implement Gemini provider with tests (TDD)

**Files:**
- Create: `backend/app/services/research/gemini_provider.py`
- Create: `backend/tests/test_gemini_provider.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_gemini_provider.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.research.gemini_provider import GeminiResearchProvider
from app.services.research.provider import ResearchResult


@pytest.fixture
def provider():
    return GeminiResearchProvider(api_key="test-key", model="gemini-2.0-flash")


@pytest.mark.asyncio
async def test_research_ticker_bullish(provider):
    mock_response = MagicMock()
    mock_response.text = '{"sentiment": "Bullish", "summary": "Strong sector momentum and positive earnings outlook."}'

    with patch.object(provider, "_client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        result = await provider.research_ticker(
            ticker="XLK", name="Technology Select Sector SPDR Fund",
            signal="Buy", current_price=220.0,
            risk_range_low=210.0, risk_range_high=230.0,
        )

    assert isinstance(result, ResearchResult)
    assert result.sentiment == "Bullish"
    assert "momentum" in result.summary.lower() or len(result.summary) > 0


@pytest.mark.asyncio
async def test_research_ticker_bearish(provider):
    mock_response = MagicMock()
    mock_response.text = '{"sentiment": "Bearish", "summary": "Sector rotation risk and upcoming Fed rate decision."}'

    with patch.object(provider, "_client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        result = await provider.research_ticker(
            ticker="XLK", name="Technology Select Sector SPDR Fund",
            signal="Buy", current_price=220.0,
            risk_range_low=210.0, risk_range_high=230.0,
        )

    assert result.sentiment == "Bearish"
    assert len(result.summary) > 0


@pytest.mark.asyncio
async def test_research_ticker_malformed_json(provider):
    mock_response = MagicMock()
    mock_response.text = "This is not JSON at all"

    with patch.object(provider, "_client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        result = await provider.research_ticker(
            ticker="XLK", name="Technology Select Sector SPDR Fund",
            signal="Buy", current_price=220.0,
            risk_range_low=210.0, risk_range_high=230.0,
        )

    assert result.sentiment == "Neutral"
    assert "unable" in result.summary.lower() or len(result.summary) > 0


@pytest.mark.asyncio
async def test_research_ticker_api_error(provider):
    with patch.object(provider, "_client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(side_effect=Exception("API error"))
        result = await provider.research_ticker(
            ticker="XLK", name="Technology Select Sector SPDR Fund",
            signal="Buy", current_price=220.0,
            risk_range_low=210.0, risk_range_high=230.0,
        )

    assert result.sentiment == "Neutral"
    assert "unavailable" in result.summary.lower() or "error" in result.summary.lower()
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/alex/InvestmentHelper/backend && python -m pytest tests/test_gemini_provider.py -v`

Expected: FAIL (module not found)

**Step 3: Install test dependency**

Run: Add `"pytest-asyncio>=0.24"` to the dev dependencies in `pyproject.toml`:

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.2",
    "pytest-asyncio>=0.24",
]
```

Run: `cd /home/alex/InvestmentHelper && uv sync`

**Step 4: Implement GeminiResearchProvider**

Create `backend/app/services/research/gemini_provider.py`:

```python
import json
from google import genai
from google.genai import types

from app.services.research.provider import ResearchProvider, ResearchResult


RESEARCH_SYSTEM_PROMPT = """You are a financial research assistant. For the given ETF, search for:
1. Recent news about the ETF and its sector (last 1-2 weeks)
2. Upcoming earnings dates, dividend dates, or rebalancing events
3. Broad market or macroeconomic conditions that could affect this ETF

Based on your findings, respond with a JSON object:
{
  "sentiment": "Bullish" | "Bearish" | "Neutral",
  "summary": "1-2 sentence summary of key findings that could affect the price"
}

Rules:
- "Bullish" means news/events support price going up
- "Bearish" means news/events suggest price pressure or downside risk
- "Neutral" means no significant news or mixed signals
- Keep the summary concise and actionable for a trader
- Focus on facts, not speculation
- Always respond with valid JSON only, no other text
"""


class GeminiResearchProvider(ResearchProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def research_ticker(
        self,
        ticker: str,
        name: str,
        signal: str,
        current_price: float,
        risk_range_low: float,
        risk_range_high: float,
    ) -> ResearchResult:
        prompt = (
            f"Research ETF: {ticker} ({name})\n"
            f"Current price: ${current_price:.2f}\n"
            f"Risk range: ${risk_range_low:.2f} - ${risk_range_high:.2f}\n"
            f"Current mechanical signal: {signal}\n\n"
            f"Search for recent news, upcoming events, and macro conditions "
            f"that could affect this ETF's price."
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=RESEARCH_SYSTEM_PROMPT,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            return self._parse_response(response.text)
        except Exception as e:
            print(f"Gemini research error for {ticker}: {e}")
            return ResearchResult(
                sentiment="Neutral",
                summary=f"Research unavailable for {ticker}.",
            )

    def _parse_response(self, text: str) -> ResearchResult:
        try:
            data = json.loads(text)
            sentiment = data.get("sentiment", "Neutral")
            if sentiment not in ("Bullish", "Bearish", "Neutral"):
                sentiment = "Neutral"
            summary = data.get("summary", "No summary available.")
            return ResearchResult(sentiment=sentiment, summary=summary)
        except (json.JSONDecodeError, KeyError, TypeError):
            return ResearchResult(
                sentiment="Neutral",
                summary="Unable to parse research results.",
            )
```

**Step 5: Run tests to verify they pass**

Run: `cd /home/alex/InvestmentHelper/backend && python -m pytest tests/test_gemini_provider.py -v`

Expected: 4 passed

**Step 6: Commit**

```bash
git add backend/app/services/research/gemini_provider.py backend/tests/test_gemini_provider.py pyproject.toml uv.lock
git commit -m "feat: implement GeminiResearchProvider with tests"
```

---

### Task 5: Create research service (orchestrator) with tests (TDD)

**Files:**
- Create: `backend/app/services/research/research_service.py`
- Create: `backend/tests/test_research_service.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_research_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from app.services.research.research_service import ResearchService
from app.services.research.provider import ResearchResult


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.research_ticker = AsyncMock(
        return_value=ResearchResult(sentiment="Bullish", summary="Positive outlook.")
    )
    return provider


@pytest.fixture
def service(mock_provider):
    return ResearchService(provider=mock_provider, expiry_hours=24)


def _make_position(ticker, signal, current_price=100.0, name="Test ETF",
                    risk_range_low=95.0, risk_range_high=115.0):
    return {
        "ticker": ticker,
        "signal": signal,
        "current_price": current_price,
        "name": name,
        "risk_range_low": risk_range_low,
        "risk_range_high": risk_range_high,
    }


@pytest.mark.asyncio
async def test_research_filters_to_buy_sell(service, mock_provider):
    positions = [
        _make_position("XLK", "Buy"),
        _make_position("XLE", "Sell"),
        _make_position("SPY", "Hold"),
        _make_position("QQQ", "Stay"),
    ]

    with patch("app.services.research.research_service.ETFResearch") as mock_model:
        mock_model.return_value.save = MagicMock()
        results = await service.research_positions("user-1", positions)

    assert len(results) == 2
    assert mock_provider.research_ticker.call_count == 2
    tickers_researched = [call.kwargs["ticker"] for call in mock_provider.research_ticker.call_args_list]
    assert "XLK" in tickers_researched
    assert "XLE" in tickers_researched


@pytest.mark.asyncio
async def test_research_saves_to_dynamo(service, mock_provider):
    positions = [_make_position("XLK", "Buy")]

    with patch("app.services.research.research_service.ETFResearch") as mock_model:
        mock_instance = MagicMock()
        mock_model.return_value = mock_instance
        await service.research_positions("user-1", positions)

    mock_instance.save.assert_called_once()


@pytest.mark.asyncio
async def test_research_returns_results(service, mock_provider):
    positions = [_make_position("XLK", "Buy")]

    with patch("app.services.research.research_service.ETFResearch") as mock_model:
        mock_model.return_value.save = MagicMock()
        results = await service.research_positions("user-1", positions)

    assert len(results) == 1
    assert results[0]["ticker"] == "XLK"
    assert results[0]["sentiment"] == "Bullish"
    assert results[0]["summary"] == "Positive outlook."


@pytest.mark.asyncio
async def test_get_cached_research_filters_expired(service):
    now = datetime.now(timezone.utc)
    fresh = MagicMock()
    fresh.ticker = "XLK"
    fresh.sentiment = "Bullish"
    fresh.summary = "Fresh research."
    fresh.researched_at = now - timedelta(hours=2)

    stale = MagicMock()
    stale.ticker = "XLE"
    stale.sentiment = "Bearish"
    stale.summary = "Stale research."
    stale.researched_at = now - timedelta(hours=25)

    with patch("app.services.research.research_service.ETFResearch") as mock_model:
        mock_model.query.return_value = [fresh, stale]
        results = service.get_cached_research("user-1")

    assert len(results) == 1
    assert results["XLK"]["sentiment"] == "Bullish"
    assert "XLE" not in results
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/alex/InvestmentHelper/backend && python -m pytest tests/test_research_service.py -v`

Expected: FAIL (module not found)

**Step 3: Implement ResearchService**

Create `backend/app/services/research/research_service.py`:

```python
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List

from app.models.etf_research import ETFResearch
from app.services.research.provider import ResearchProvider


class ResearchService:
    def __init__(self, provider: ResearchProvider, expiry_hours: int = 24):
        self._provider = provider
        self._expiry_hours = expiry_hours

    async def research_positions(
        self, user_id: str, positions: List[dict]
    ) -> List[dict]:
        actionable = [p for p in positions if p["signal"] in ("Buy", "Sell")]

        tasks = [
            self._research_and_save(user_id, p) for p in actionable
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = []
        for pos, result in zip(actionable, results):
            if isinstance(result, Exception):
                print(f"Research failed for {pos['ticker']}: {result}")
                continue
            output.append(result)
        return output

    async def _research_and_save(self, user_id: str, position: dict) -> dict:
        result = await self._provider.research_ticker(
            ticker=position["ticker"],
            name=position.get("name", ""),
            signal=position["signal"],
            current_price=position["current_price"],
            risk_range_low=position["risk_range_low"],
            risk_range_high=position["risk_range_high"],
        )

        now = datetime.now(timezone.utc)
        record = ETFResearch(
            user_id=user_id,
            ticker=position["ticker"],
            sentiment=result.sentiment,
            summary=result.summary,
            signal_at_research=position["signal"],
            researched_at=now,
        )
        record.save()

        return {
            "ticker": position["ticker"],
            "sentiment": result.sentiment,
            "summary": result.summary,
            "researched_at": now.isoformat(),
        }

    def get_cached_research(self, user_id: str) -> Dict[str, dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self._expiry_hours)
        results = {}
        try:
            for item in ETFResearch.query(user_id):
                if item.researched_at >= cutoff:
                    results[item.ticker] = {
                        "sentiment": item.sentiment,
                        "summary": item.summary,
                        "researched_at": item.researched_at.isoformat(),
                    }
        except Exception as e:
            print(f"Error fetching cached research for {user_id}: {e}")
        return results
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/alex/InvestmentHelper/backend && python -m pytest tests/test_research_service.py -v`

Expected: 4 passed

**Step 5: Commit**

```bash
git add backend/app/services/research/research_service.py backend/tests/test_research_service.py
git commit -m "feat: implement ResearchService orchestrator with tests"
```

---

### Task 6: Add schemas and update PositionResponse

**Files:**
- Modify: `backend/app/schemas/portfolio.py:1-27`

**Step 1: Add ResearchResponse and update PositionResponse**

In `backend/app/schemas/portfolio.py`, add `ResearchResponse` before `PositionResponse` and add the `research` field:

```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class HoldingResponse(BaseModel):
    ticker: str
    shares: float
    cost_basis: float


class RecommendationResponse(BaseModel):
    signal: str
    shares_to_trade: float
    target_position_value: float
    current_position_value: float
    penetration_depth: float


class ResearchResponse(BaseModel):
    sentiment: str
    summary: str
    researched_at: datetime


class PositionResponse(BaseModel):
    ticker: str
    name: Optional[str] = None
    current_price: Optional[float] = None
    open_price: Optional[float] = None
    risk_range_low: Optional[float] = None
    risk_range_high: Optional[float] = None
    shares: float
    recommendation: Optional[RecommendationResponse] = None
    research: Optional[ResearchResponse] = None
```

**Step 2: Run existing tests to confirm nothing breaks**

Run: `cd /home/alex/InvestmentHelper/backend && python -m pytest tests/ -v`

Expected: All pass

**Step 3: Commit**

```bash
git add backend/app/schemas/portfolio.py
git commit -m "feat: add ResearchResponse schema and research field to PositionResponse"
```

---

### Task 7: Create research router and register it

**Files:**
- Create: `backend/app/routers/research.py`
- Modify: `backend/app/main.py:45-57`

**Step 1: Create the research router**

Create `backend/app/routers/research.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.core.dependencies import get_current_active_user
from app.core.config import settings
from app.models.portfolio import Portfolio
from app.models.etf import ETF
from app.schemas.portfolio import ResearchResponse
from app.schemas.etf import ErrorResponse
from app.services.recommendation_service import compute_recommendation
from app.services.research.gemini_provider import GeminiResearchProvider
from app.services.research.research_service import ResearchService
from app.models.trading_rules import TradingRules, DEFAULT_MAX_POSITION_PCT, DEFAULT_MIN_POSITION_PCT
from pynamodb.exceptions import DoesNotExist

router = APIRouter(
    prefix="/portfolio",
    tags=["Research"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


def _get_research_service() -> ResearchService:
    provider = GeminiResearchProvider(
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL,
    )
    return ResearchService(
        provider=provider,
        expiry_hours=settings.RESEARCH_EXPIRY_HOURS,
    )


@router.post("/research", response_model=List[ResearchResponse])
async def research_positions(
    current_user: dict = Depends(get_current_active_user),
):
    user_id = current_user["user_id"]

    try:
        portfolio = Portfolio.get(user_id)
    except DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    except Exception as e:
        print(f"Error fetching portfolio for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching portfolio",
        )

    # Compute total value
    total_value = 0.0
    enriched = []
    for holding in portfolio.holdings:
        try:
            etf = ETF.get(holding.ticker)
            price = etf.current_price or 0
            position_value = price * holding.shares
            total_value += position_value
            enriched.append({
                "ticker": holding.ticker,
                "name": etf.name or "",
                "current_price": price,
                "risk_range_low": getattr(etf, "risk_range_low", None),
                "risk_range_high": getattr(etf, "risk_range_high", None),
                "shares": holding.shares,
                "position_value": position_value,
            })
        except Exception:
            continue

    if total_value <= 0:
        return []

    # Fetch trading rules
    try:
        rules = TradingRules.get(user_id)
        max_position_pct = float(rules.max_position_pct)
        min_position_pct = float(rules.min_position_pct)
    except DoesNotExist:
        max_position_pct = DEFAULT_MAX_POSITION_PCT
        min_position_pct = DEFAULT_MIN_POSITION_PCT
    except Exception:
        max_position_pct = DEFAULT_MAX_POSITION_PCT
        min_position_pct = DEFAULT_MIN_POSITION_PCT

    # Compute signals and build research input
    research_input = []
    for pos in enriched:
        if (
            pos["current_price"] > 0
            and pos["risk_range_low"] is not None
            and pos["risk_range_high"] is not None
            and pos["risk_range_high"] - pos["risk_range_low"] > 0
        ):
            rec = compute_recommendation(
                current_price=pos["current_price"],
                risk_range_low=pos["risk_range_low"],
                risk_range_high=pos["risk_range_high"],
                current_position_value=pos["position_value"],
                portfolio_value=total_value,
                max_position_pct=max_position_pct,
                min_position_pct=min_position_pct,
            )
            pos["signal"] = rec.signal

    service = _get_research_service()
    try:
        results = await service.research_positions(user_id, research_input)
    except Exception as e:
        print(f"Research error for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during research",
        )

    return [
        ResearchResponse(
            sentiment=r["sentiment"],
            summary=r["summary"],
            researched_at=r["researched_at"],
        )
        for r in results
    ]
```

**Step 2: Register the router in main.py**

In `backend/app/main.py`, add the import and include_router call. After the existing router imports, add:

```python
from app.routers import research
```

After the existing `include_router` calls, add:

```python
app.include_router(
    research.router,
    prefix=settings.API_V1_STR,
)
```

**Step 3: Commit**

```bash
git add backend/app/routers/research.py backend/app/main.py
git commit -m "feat: add POST /portfolio/research endpoint"
```

---

### Task 8: Update portfolio router to include cached research

**Files:**
- Modify: `backend/app/routers/portfolio.py:92-124`

**Step 1: Add cached research to GET /portfolio response**

In `backend/app/routers/portfolio.py`, add imports at the top:

```python
from app.schemas.portfolio import PortfolioResponse, PositionResponse, RecommendationResponse, ResearchResponse, UploadResponse, UploadHoldingResponse
from app.services.research.gemini_provider import GeminiResearchProvider
from app.services.research.research_service import ResearchService
from app.core.config import settings
```

After the recommendation computation loop (after line 117 `pos.recommendation = RecommendationResponse(...)`) and before the `initial_value` line, add:

```python
    # Attach cached research
    service = ResearchService(
        provider=GeminiResearchProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
        ),
        expiry_hours=settings.RESEARCH_EXPIRY_HOURS,
    )
    cached = service.get_cached_research(user_id)
    for pos in positions:
        if pos.ticker in cached:
            r = cached[pos.ticker]
            pos.research = ResearchResponse(
                sentiment=r["sentiment"],
                summary=r["summary"],
                researched_at=r["researched_at"],
            )
```

**Step 2: Run all tests**

Run: `cd /home/alex/InvestmentHelper/backend && python -m pytest tests/ -v`

Expected: All pass

**Step 3: Commit**

```bash
git add backend/app/routers/portfolio.py
git commit -m "feat: include cached research in GET /portfolio response"
```

---

### Task 9: Frontend types and research hook

**Files:**
- Modify: `frontend/src/types/index.ts:1-18`
- Create: `frontend/src/hooks/useResearch.ts`

**Step 1: Add Research interface and update ETFPosition**

In `frontend/src/types/index.ts`, add the `Research` interface after `Recommendation` and add the `research` field to `ETFPosition`:

```typescript
export interface Recommendation {
  signal: string;
  shares_to_trade: number;
  target_position_value: number;
  current_position_value: number;
  penetration_depth: number;
}

export interface Research {
  sentiment: string;
  summary: string;
  researched_at: string;
}

export interface ETFPosition {
  ticker: string;
  name: string | null;
  current_price: number | null;
  open_price: number | null;
  risk_range_low: number | null;
  risk_range_high: number | null;
  shares: number;
  recommendation: Recommendation | null;
  research: Research | null;
}
```

**Step 2: Create the useResearch hook**

Create `frontend/src/hooks/useResearch.ts`:

```typescript
import { useState, useCallback } from "react";
import { useAuth } from "@clerk/clerk-react";
import { apiFetch } from "../api/client";
import type { Research } from "../types";

export function useResearch() {
  const { getToken } = useAuth();
  const [researching, setResearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const triggerResearch = useCallback(async () => {
    setResearching(true);
    setError(null);
    try {
      await apiFetch<Research[]>("/api/v1/portfolio/research", getToken, {
        method: "POST",
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Research failed");
    } finally {
      setResearching(false);
    }
  }, [getToken]);

  return { researching, error, triggerResearch };
}
```

**Step 3: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/hooks/useResearch.ts
git commit -m "feat: add Research type and useResearch hook"
```

---

### Task 10: Frontend UI — Dashboard button and ETFRow research display

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx:1-132`
- Modify: `frontend/src/components/etf/ETFRow.tsx:1-151`

**Step 1: Add "Search for data" button to Dashboard**

In `frontend/src/pages/Dashboard.tsx`:

Add the import:
```typescript
import { useResearch } from "../hooks/useResearch";
```

Add the hook inside the component (after the `useTradingRules` line):
```typescript
const { researching, error: researchError, triggerResearch } = useResearch();
```

Create a handler that triggers research then refetches portfolio:
```typescript
const handleResearch = async () => {
  await triggerResearch();
  refetch();
};
```

Add the button in the header `div` (the one with `flex items-center gap-3`), before the upload button:
```tsx
{researchError && (
  <span className="text-red-400 text-xs font-mono">
    {researchError}
  </span>
)}
<button
  type="button"
  onClick={handleResearch}
  disabled={researching || loading}
  className="px-3 py-1.5 border border-gray-700 rounded text-xs font-mono text-gray-300 hover:text-blue-400 hover:border-blue-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
>
  {researching ? "SEARCHING..." : "SEARCH FOR DATA"}
</button>
```

**Step 2: Add inline research display to ETFRow**

In `frontend/src/components/etf/ETFRow.tsx`:

Add a helper function for sentiment badge color (near `getRecommendationColor`):

```typescript
function getSentimentColor(sentiment: string): string {
  switch (sentiment) {
    case "Bullish": return "text-green-400";
    case "Bearish": return "text-red-400";
    case "Neutral": return "text-yellow-400";
    default: return "text-gray-400";
  }
}

function formatResearchAge(researched_at: string): string {
  const diffMs = Date.now() - new Date(researched_at).getTime();
  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  if (hours < 1) return "just now";
  if (hours === 1) return "1h ago";
  return `${hours}h ago`;
}
```

Destructure `research` from `position` in the existing destructure block:
```typescript
const {
  ticker, name, current_price, open_price,
  risk_range_low, risk_range_high, recommendation, research,
} = position;
```

After the closing `</div>` of the `flex flex-col md:flex-row` container (before the closing `</button>`), add:

```tsx
{research && (
  <div className="mt-2 pt-2 border-t border-gray-800 text-xs">
    <span className={`${getSentimentColor(research.sentiment)} font-bold`}>
      {research.sentiment}
    </span>
    <span className="text-gray-400">
      {" · "}{research.summary}
    </span>
    <span className="text-gray-600 ml-2">
      {formatResearchAge(research.researched_at)}
    </span>
  </div>
)}
```

**Step 3: Run the frontend build**

Run: `cd /home/alex/InvestmentHelper/frontend && npm run build`

Expected: No TypeScript errors

**Step 4: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx frontend/src/components/etf/ETFRow.tsx
git commit -m "feat: add Search for Data button and inline research display"
```

---

### Task 11: Final verification

**Step 1: Run all backend tests**

Run: `cd /home/alex/InvestmentHelper/backend && python -m pytest tests/ -v`

Expected: All pass (recommendation tests + gemini provider tests + research service tests)

**Step 2: Run frontend build**

Run: `cd /home/alex/InvestmentHelper/frontend && npm run build`

Expected: No errors

**Step 3: Review the research router for a bug**

In `backend/app/routers/research.py`, verify that positions are only added to `research_input` when they have Buy/Sell signals. The current code computes `rec.signal` and sets `pos["signal"]` but doesn't append to `research_input`. Fix: add `research_input.append(pos)` after setting the signal, but only for Buy/Sell:

```python
            pos["signal"] = rec.signal
            if rec.signal in ("Buy", "Sell"):
                research_input.append(pos)
```

Run tests again after fixing.

**Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: ensure research router filters to Buy/Sell signals"
```
