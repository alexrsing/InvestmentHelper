# DynamoDB Module - Price Fetcher Tables
# Creates DynamoDB tables for the price fetcher service

# =============================================================================
# Watchlist Table
# Manages which symbols the price fetcher tracks
# =============================================================================

resource "aws_dynamodb_table" "watchlist" {
  name         = "watchlist"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "symbol"

  attribute {
    name = "symbol"
    type = "S"
  }

  # Global secondary index for querying by symbol_type
  global_secondary_index {
    name            = "symbol_type-index"
    hash_key        = "symbol_type"
    projection_type = "ALL"
  }

  attribute {
    name = "symbol_type"
    type = "S"
  }

  # Enable point-in-time recovery for data protection
  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  # TTL not needed for watchlist (permanent records)

  tags = merge(var.tags, {
    Environment = var.environment
    Module      = "dynamodb"
    Table       = "watchlist"
  })
}

# =============================================================================
# Prices Table (optional - shared with InvestmentHelper backend as 'etfs')
# =============================================================================

resource "aws_dynamodb_table" "prices" {
  count = var.create_prices_table ? 1 : 0

  name         = "etfs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "etf_symbol"

  attribute {
    name = "etf_symbol"
    type = "S"
  }

  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  tags = merge(var.tags, {
    Environment = var.environment
    Module      = "dynamodb"
    Table       = "prices"
  })
}

# =============================================================================
# Config Table (optional - price fetcher configuration)
# =============================================================================

resource "aws_dynamodb_table" "config" {
  count = var.create_config_table ? 1 : 0

  name         = "price_fetcher_config"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "config_type"
  range_key    = "config_key"

  attribute {
    name = "config_type"
    type = "S"
  }

  attribute {
    name = "config_key"
    type = "S"
  }

  # TTL for config entries (e.g., cached holidays)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  tags = merge(var.tags, {
    Environment = var.environment
    Module      = "dynamodb"
    Table       = "config"
  })
}
