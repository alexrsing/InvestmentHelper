# Claude Code Context

> See [README.md](README.md) for general project documentation, setup instructions, and infrastructure overview.
> See [GitHub Issues](https://github.com/sing-email/price-fetcher/issues) for recent changes and planned work.

## Project Structure

```
price-fetcher/
├── lambda_handler.py          # AWS Lambda entry points (3 handlers)
├── fetchers/                   # Core fetcher modules
│   ├── main.py                 # PriceDataFetcher class, CLI entry point
│   ├── models.py               # PynamoDB models (ETF, ETFHistory)
│   ├── db_service.py           # DynamoDB operations via PynamoDB + boto3
│   ├── logging_config.py       # Structured logging (JSON for Lambda)
│   ├── api_keys.py             # API key/config loading (single JSON secret → env fallback)
│   ├── config_service.py       # DynamoDB config storage (holidays, settings)
│   ├── timeout.py              # Lambda timeout monitoring, graceful exit
│   ├── batch.py                # Batch processing, symbol limiting
│   ├── rate_limit.py           # Lambda-aware rate limiting (shorter delays)
│   ├── yf_service.py           # Yahoo Finance - free, primary source
│   ├── av_service.py           # Alpha Vantage - paid, with tier support
│   ├── td_service.py           # Twelve Data - paid
│   ├── fh_service.py           # Finnhub - paid
│   ├── fmp_service.py          # Financial Modeling Prep - paid
│   └── core/
│       ├── holiday_fetcher.py  # Market holiday calendar updates
│       └── validator.py        # Price data completeness validation
├── src/pricedata/              # Public API package
│   ├── client.py               # get_price(), is_market_holiday(), load_holidays()
│   ├── db_service.py           # DynamoDB service (mirrors fetchers/db_service.py)
│   └── secure_logging.py       # API key masking in logs
├── scripts/                    # CLI utilities
│   ├── fetch_prices.py         # Manual price fetch
│   ├── fetch_holidays.py       # Update holiday calendar
│   ├── validate_prices.py      # Check data completeness
│   ├── get_price.py            # Query single symbol price
│   ├── import_stockanalysis.py # Import from stockanalysis.com
│   └── migrate_holidays_to_dynamodb.py  # One-time migration script
├── config/                     # Sample configuration files
├── infrastructure/             # Terraform IaC
│   ├── bootstrap/              # S3 state bucket, DynamoDB lock table
│   ├── modules/                # lambda, iam, secrets, scheduler, monitoring, github-oidc
│   └── environments/           # dev, staging, prod tfvars
└── deployment/                 # Deployment scripts
```

## Key Modules

### fetchers/main.py - PriceDataFetcher
```python
class PriceDataFetcher:
    def get_info(symbol: str) -> Tuple[Optional[Dict], str]
    def get_historical_data(symbol: str, period: str, interval: str) -> Tuple[Optional[List], str]
    def fetch_prices(symbols: List[str], context=None, db_service=None) -> Dict[str, Any]
    def get_api_status() -> Dict[str, Any]
```
Data source priority (auto mode): yfinance → twelvedata → alphavantage → finnhub → fmp

### lambda_handler.py
```python
def handler(event, context) -> Dict        # Main price fetcher
def holiday_handler(event, context) -> Dict # Holiday calendar updates
def validator_handler(event, context) -> Dict # Price data validation
```

### fetchers/timeout.py
```python
class LambdaTimeoutMonitor:
    remaining_seconds: float
    should_stop: bool
    def check_timeout(operation: str) -> None  # Raises TimeoutApproaching

def timeout_aware_processing(context, buffer_seconds=60)  # Context manager
```

### fetchers/api_keys.py
```python
def get_api_key(key_name: str) -> Optional[str]
# In Lambda: loads all keys/tiers from single JSON secret (PRICE_FETCHER_SECRET_NAME)
# Locally: falls back to os.getenv()
# Rejects placeholder values starting with "your_"
def is_api_key_configured(key_name: str) -> bool
def clear_cache() -> None  # Reset for testing
```

### fetchers/config_service.py
```python
class ConfigService:
    def get_config(config_type: str, config_key: str) -> Optional[Dict]
    def put_config(config_type: str, config_key: str, data: Any, ttl_seconds: int = None)

def get_cached_config(config_type: str, config_key: str) -> Optional[Dict]  # LRU cached
```

### src/pricedata/client.py
```python
def get_price(symbol: str, target_date: date) -> Optional[float]
def get_price_history(symbol: str, start_date: date, end_date: date) -> Dict[date, float]
def get_current_price(symbol: str) -> Optional[float]
def is_market_holiday(target_date: date) -> bool
def is_trading_day(target_date: date) -> bool
def load_holidays() -> dict  # DynamoDB-first, file fallback
```

## DynamoDB Tables

All tables use flat names (no environment prefix), matching the InvestmentHelper convention.
Written via PynamoDB models (`fetchers/models.py`), matching `backend/app/models/etf.py`.

### etfs
ETF data storage (shared with InvestmentHelper backend). Written via PynamoDB.
- PK: `ticker`
- Attributes: `name`, `current_price`, `open_price`, `risk_range_low`, `risk_range_high`, `created_at`, `updated_at`
- Override via env var: `PRICES_TABLE`

### etf_history
Daily OHLCV price history per ETF. Written via PynamoDB.
- PK: `ticker`, SK: `date` (YYYY-MM-DD)
- Attributes: `open_price`, `high_price`, `low_price`, `close_price`, `adjusted_close`, `volume`, `risk_range_low`, `risk_range_high`, `created_at`

### watchlist
Symbols to track for price fetching.
- PK: `symbol`
- Attributes: `symbol_type`, `enabled`, `priority`, `added_at`, `added_by`, `metadata`
- Override via env var: `WATCHLIST_TABLE`

### price_fetcher_config
Configuration storage (holidays, settings).
- PK: `config_type` (e.g., "holidays")
- SK: `config_key` (e.g., "US")
- Attributes: `data`, `updated_at`, `ttl`
- Override via env var: `CONFIG_TABLE_NAME`

## Lambda Response Codes

- `200` - All symbols processed successfully
- `206` - Partial content (timeout triggered, remaining symbols in response)
- `207` - Multi-status (some symbols failed)
- `500` - Handler error

## Architecture Decisions

### Lambda Optimizations
- **No filesystem**: Config stored in DynamoDB, not JSON files
- **Timeout handling**: Graceful exit 60s before timeout via `timeout.py`
- **Container reuse**: `lru_cache` decorators and singleton patterns
- **Secrets Manager**: All API keys and tiers loaded from single JSON secret (`PRICE_FETCHER_SECRET_NAME`)
- **Reduced retries**: Shorter backoff in Lambda (max 30s vs 160s locally)

### Caching Strategy
- `api_keys.py`: Module-level `_secrets_cache` dict (loaded once from Secrets Manager in Lambda)
- `config_service.py`: `lru_cache` on `get_cached_config()`
- `client.py`: Module-level `_holidays_cache`

### Data Source Fallback
In `auto` mode, sources tried in order until valid price returned:
1. Yahoo Finance (free, no API key)
2. Twelve Data
3. Alpha Vantage
4. Finnhub
5. Financial Modeling Prep

## Common Commands

```bash
# Run locally
cd fetchers && python main.py --force

# Run tests
python -m pytest src/tests/ -v

# Check syntax
python3 -m py_compile fetchers/*.py lambda_handler.py

# Migrate holidays to DynamoDB
python scripts/migrate_holidays_to_dynamodb.py --dry-run
python scripts/migrate_holidays_to_dynamodb.py

# Deploy infrastructure
cd infrastructure
terraform init -backend-config=environments/dev/backend-config.hcl
terraform apply -var-file=environments/dev/terraform.tfvars
```
