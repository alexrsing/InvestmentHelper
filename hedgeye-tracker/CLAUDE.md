# hedgeye-tracker

Hedgeye risk range email parser and DynamoDB updater. Parses daily RISK RANGE SIGNALS and weekly ETF Pro Plus emails from Gmail, extracts buy/sell trade ranges and trend ranges, and saves them to DynamoDB.

## Commands

```bash
# Install dependencies (using uv)
cd hedgeye-tracker && uv sync

# Install dev dependencies (for testing)
cd hedgeye-tracker && uv sync --extra dev

# Run locally (CLI mode)
cd hedgeye-tracker/src && python main.py
cd hedgeye-tracker/src && python main.py --skip-validation

# Run tests
cd hedgeye-tracker && python -m pytest tests/ -v

# Syntax check
cd hedgeye-tracker && python3 -m py_compile lambda_handler.py src/models.py src/services/etf_update_service.py
```

## Architecture

### Data Flow

```
Gmail (Hedgeye emails)
       |
[hedgeye-tracker Lambda]
       |
  Parse daily RISK RANGE     Parse weekly ETF Pro Plus
  SIGNALS emails              emails
       |                         |
  TradeRangeTransformer     TrendRangeTransformer
  + SymbolMapping           + SymbolMapping
       |                         |
  +----+--------+           hedgeye_weekly_ranges
  |             |           (own table, history only)
  v             v
etfs table   hedgeye_daily_ranges
(shared)     (own table, history)
risk_range_low/_high
```

### Key Modules

- **`lambda_handler.py`** — AWS Lambda entry point; configures structured logging, orchestrates Gmail fetch -> parse -> transform -> save
- **`src/main.py`** — CLI entry point with dotenv loading, startup validation, same flow as Lambda
- **`src/models.py`** — PynamoDB models for shared `etfs` and `etf_history` tables (read/update only)
- **`src/handlers/database.py`** — Database handler; saves to hedgeye tables AND updates shared etfs table via ETFUpdateService
- **`src/handlers/gmail.py`** — Gmail handler; fetches risk range and trend range emails
- **`src/services/etf_update_service.py`** — Partial updates on shared etfs table (risk_range_low/high only)
- **`src/services/database_service.py`** — Low-level DynamoDB operations (boto3)
- **`src/services/gmail_service.py`** — Gmail API client with service account auth via AWS Secrets Manager
- **`src/services/risk_range_parser_service.py`** — HTML parser for daily RISK RANGE SIGNALS emails
- **`src/services/trend_range_parser_service.py`** — HTML parser for weekly ETF Pro Plus emails
- **`src/services/trade_range_transformer.py`** — Transforms parsed risk range data for DB storage
- **`src/services/trend_range_transformer.py`** — Transforms parsed trend range data for DB storage
- **`src/services/symbol_mapping_service.py`** — Maps index symbols (SPX->SPY, COMPQ->QQQ) to tradable ETFs
- **`src/services/price_ratio_calculator.py`** — Calculates price ratios for mapped symbols
- **`src/util/logging_config.py`** — Structured logging (JSON for Lambda, human-readable for CLI)
- **`src/util/secure_logging.py`** — Email/credential masking for safe logging
- **`src/util/startup_validation.py`** — Validates AWS credentials, Gmail config before processing

### DynamoDB Tables

| Table | Owner | Access |
|-------|-------|--------|
| `etfs` | price-fetcher | hedgeye-tracker updates `risk_range_low`/`risk_range_high` only (partial update) |
| `etf_history` | price-fetcher | hedgeye-tracker updates `risk_range_low`/`risk_range_high` (partial update) |
| `hedgeye_daily_ranges` | hedgeye-tracker | Full read/write — daily trade range history |
| `hedgeye_weekly_ranges` | hedgeye-tracker | Full read/write — weekly trend range history |

### Auth

Gmail access uses a Google service account with domain-wide delegation. Credentials stored in AWS Secrets Manager at `{env}/hedgeye/gmail-service-account`.

### Key Design Decisions

1. **Partial updates only** — Never overwrites price fields on the shared etfs table
2. **Skip missing tickers** — If ticker isn't in etfs table, logs warning and skips (price-fetcher must create it first)
3. **Daily ranges -> shared table** — buy_trade = risk_range_low, sell_trade = risk_range_high
4. **Weekly ranges -> own table only** — NOT written to the shared etfs table
5. **Flat table names** — No environment prefix (matches InvestmentHelper convention)
