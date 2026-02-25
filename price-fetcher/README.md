# Price Fetcher

ETF/stock price fetcher with multi-source support, designed for AWS Lambda deployment.

## Features

- **Multi-source price fetching**: Yahoo Finance (free), Alpha Vantage, Twelve Data, Finnhub, Financial Modeling Prep
- **Automatic fallback**: Tries sources in order until valid data is returned
- **AWS Lambda optimized**: Timeout handling, batch processing, Secrets Manager integration
- **Structured logging**: JSON format for CloudWatch Insights
- **Market holiday awareness**: DynamoDB-backed holiday calendar

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Run price fetcher locally
cd fetchers && python main.py

# Run with force refresh
cd fetchers && python main.py --force
```

## Configuration

### Environment Variables

```bash
# Data source (auto tries all in order)
DATA_SOURCE=auto  # auto|yfinance|alphavantage|twelvedata|finnhub|fmp

# API Keys (for local development)
ALPHA_VANTAGE_API_KEY=your_key
TWELVEDATA_API_KEY=your_key
FINNHUB_API_KEY=your_key
FMP_API_KEY=your_key

# Fetcher settings
MAX_SYMBOLS_PER_RUN=50
STALENESS_THRESHOLD_MINUTES=15
TIMEOUT_BUFFER_SECONDS=60

# AWS
AWS_REGION=us-east-1
CONFIG_TABLE_NAME=price_fetcher_config
```

### Secrets Manager (Lambda)

In Lambda, all API keys and tiers are loaded from a single JSON secret. Set this env var:

```bash
PRICE_FETCHER_SECRET_NAME=prod/price-fetcher/config
```

The secret contains a JSON object with all keys and tiers:
```json
{
  "ALPHA_VANTAGE_API_KEY": "...",
  "ALPHA_VANTAGE_TIER": "free",
  "TWELVEDATA_API_KEY": "...",
  "TWELVEDATA_TIER": "free",
  "FINNHUB_API_KEY": "...",
  "FINNHUB_TIER": "free",
  "FMP_API_KEY": "...",
  "FMP_TIER": "free"
}
```

## Infrastructure

Terraform-managed AWS infrastructure with 6 modules:

| Module | Resources |
|--------|-----------|
| `lambda` | 3 Lambda functions + CloudWatch log groups |
| `iam` | Execution role with least-privilege policies |
| `secrets` | Secrets Manager for API keys |
| `scheduler` | EventBridge cron rules |
| `monitoring` | CloudWatch alarms + SNS topics |
| `github-oidc` | GitHub Actions OIDC authentication |

### Lambda Functions

| Function | Purpose | Timeout | Schedule |
|----------|---------|---------|----------|
| price-fetcher | Fetch ETF prices | 15 min | Every 15 min (market hours) |
| holiday-fetcher | Update holiday calendar | 5 min | Sundays 8 AM UTC |
| validator | Validate price data | 10 min | Weekdays 9 PM UTC |

### Deployment

```bash
# Bootstrap (one-time)
cd infrastructure/bootstrap
terraform init && terraform apply

# Deploy to dev
cd infrastructure
terraform init -backend-config=environments/dev/backend-config.hcl
terraform apply -var-file=environments/dev/terraform.tfvars
```

See `infrastructure/environments/` for dev, staging, and prod configurations.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/fetch_prices.py` | Manual price fetch |
| `scripts/fetch_holidays.py` | Update holiday calendar |
| `scripts/validate_prices.py` | Check data completeness |
| `scripts/get_price.py` | Query single symbol |
| `scripts/migrate_holidays_to_dynamodb.py` | Migrate holidays to DynamoDB |

## Development

```bash
# Run tests
python -m pytest src/tests/ -v

# Check syntax
python3 -m py_compile fetchers/*.py lambda_handler.py
```

## License

Private repository.
