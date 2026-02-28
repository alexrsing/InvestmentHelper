# Agentic Trading Recommendations Design

## Overview

Add on-demand LLM-powered research to the trading dashboard. A "Search for data" button triggers per-ticker web research via Gemini 2.0 Flash with Google Search grounding. Results display inline below ETF rows as a sentiment badge (Bullish/Bearish/Neutral) plus a 1-2 sentence summary. The LLM is advisory only — it never overrides the mechanical Buy/Sell/Hold/Stay signal.

## Requirements

- **Trigger**: "Search for data" button on dashboard, on-demand only (no automatic runs)
- **Scope**: Only ETFs with active Buy/Sell signals (not Hold/Stay)
- **Execution**: One LLM call per ticker, parallelized via `asyncio.gather`
- **LLM**: Gemini 2.0 Flash with Google Search grounding, behind a provider-agnostic interface
- **Research scope**: News headlines, macro conditions, upcoming earnings/events for each ETF
- **Output**: Sentiment (Bullish/Bearish/Neutral) + 1-2 sentence summary text
- **Authority**: Advisory only — separate from mechanical signal, user decides
- **Caching**: DynamoDB, auto-expire after 24 hours
- **Display**: Inline below ETF rows, with sentiment badge color and "Researched Xh ago" timestamp
- **Cost target**: ~$0.59/month at 50 positions/day with Gemini 2.0 Flash pricing

## Architecture

### Approach: Direct API endpoint

A new `POST /api/v1/portfolio/research` endpoint in the existing FastAPI backend. When called, it fetches the portfolio, computes mechanical recommendations, filters to Buy/Sell positions, runs parallel Gemini calls, stores results in DynamoDB, and returns them. The existing `GET /api/v1/portfolio` endpoint includes cached (non-expired) research in its response.

### Provider abstraction

```
backend/app/services/
  research/
    provider.py          # Abstract ResearchProvider interface
    gemini_provider.py   # Gemini 2.0 Flash + Google Search implementation
    research_service.py  # Orchestrator: parallel calls, caching, expiry
```

`ResearchProvider` defines one method:
```python
class ResearchResult:
    sentiment: str   # "Bullish", "Bearish", "Neutral"
    summary: str     # 1-2 sentence research summary

class ResearchProvider(ABC):
    async def research_ticker(
        self, ticker: str, name: str, signal: str, current_price: float,
        risk_range_low: float, risk_range_high: float
    ) -> ResearchResult
```

Swapping to a different LLM means adding a new provider class and changing a config value (e.g., `RESEARCH_PROVIDER=gemini` in `.env`).

### DynamoDB table: `etf_research`

| Field | Type | Description |
|-------|------|-------------|
| `user_id` (hash key) | String | Owner of the research |
| `ticker` (range key) | String | ETF ticker |
| `sentiment` | String | "Bullish", "Bearish", or "Neutral" |
| `summary` | String | 1-2 sentence research summary |
| `signal_at_research` | String | Mechanical signal when research was run |
| `researched_at` | DateTime | Timestamp, used for 24h expiry filter |

### API changes

**New endpoint**: `POST /api/v1/portfolio/research`
- Requires JWT auth
- Fetches portfolio, computes recommendations
- Filters to positions with Buy/Sell signals
- Calls `ResearchService.research_positions(positions)` (parallel Gemini calls)
- Stores results in `etf_research` table
- Returns list of `ResearchResponse` objects

**Modified endpoint**: `GET /api/v1/portfolio`
- After computing recommendations, fetches cached research from `etf_research`
- Filters out research older than 24 hours
- Attaches `research` field to each `PositionResponse`

### Schemas

```python
class ResearchResponse(BaseModel):
    sentiment: str          # "Bullish", "Bearish", "Neutral"
    summary: str
    researched_at: datetime

class PositionResponse(BaseModel):
    ...
    research: Optional[ResearchResponse] = None
```

## Frontend

### Dashboard changes

- **"Search for data" button** in the portfolio summary area. Shows loading spinner while waiting (~5-10s). Disables during search.
- **Inline research display** below each ETF row that has cached research:
  - Sentiment badge: green (Bullish), red (Bearish), yellow (Neutral)
  - 1-2 sentence summary text
  - "Researched Xh ago" timestamp
- Research older than 24h is not returned by the API (auto-expired)

### TypeScript types

```typescript
interface Research {
  sentiment: string;
  summary: string;
  researched_at: string;
}

interface ETFPosition {
  ...
  research: Research | null;
}
```

## LLM prompt design

Each per-ticker call sends a system prompt instructing the LLM to:
1. Search for recent news about the ETF and its sector
2. Check for upcoming earnings, dividend dates, rebalancing events
3. Consider broad market/macro conditions affecting this ETF
4. Return a structured response with sentiment and summary

The prompt includes the ETF's current price, risk range, and mechanical signal for context.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `RESEARCH_PROVIDER` | `gemini` | Which LLM provider to use |
| `GEMINI_API_KEY` | (secret) | Gemini API key, stored in AWS Secrets Manager |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Model ID (swap when 2.0 retires June 2026) |
| `RESEARCH_EXPIRY_HOURS` | `24` | Hours before cached research expires |

## Key decisions

- **Advisory only**: LLM sentiment is separate from mechanical signal — user decides
- **Provider-agnostic**: Abstract interface allows swapping Gemini for Claude/GPT later
- **On-demand only**: No automatic runs, no background jobs, no cost when not used
- **Buy/Sell only**: Skip Hold/Stay positions to minimize LLM calls
- **Per-ticker calls**: Better search quality and reasoning vs. batching all tickers
- **24h auto-expiry**: Prevents acting on stale research
- **Gemini 2.0 Flash**: Cheapest option with native Google Search grounding (~$0.59/month)
