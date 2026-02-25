# Lambda Module - Function Deployment
# Creates Lambda functions for price fetching, holiday updates, and validation

# Placeholder deployment package (empty zip)
# Actual code is deployed via CI/CD pipeline
data "archive_file" "placeholder" {
  type        = "zip"
  output_path = "${path.module}/placeholder.zip"

  source {
    content  = "# Placeholder - deploy actual code via CI/CD"
    filename = "placeholder.py"
  }
}

# =============================================================================
# CloudWatch Log Groups (created before Lambda to control retention)
# =============================================================================

resource "aws_cloudwatch_log_group" "price_fetcher" {
  name              = "/aws/lambda/${var.environment}-price-fetcher"
  retention_in_days = var.log_retention_days

  tags = {
    Environment = var.environment
    Module      = "lambda"
    Function    = "price-fetcher"
  }
}

resource "aws_cloudwatch_log_group" "holiday_fetcher" {
  name              = "/aws/lambda/${var.environment}-price-fetcher-holidays"
  retention_in_days = var.log_retention_days

  tags = {
    Environment = var.environment
    Module      = "lambda"
    Function    = "holiday-fetcher"
  }
}

resource "aws_cloudwatch_log_group" "validator" {
  name              = "/aws/lambda/${var.environment}-price-fetcher-validator"
  retention_in_days = var.log_retention_days

  tags = {
    Environment = var.environment
    Module      = "lambda"
    Function    = "validator"
  }
}

# =============================================================================
# Lambda Functions
# =============================================================================

# Main Price Fetcher
resource "aws_lambda_function" "price_fetcher" {
  function_name = "${var.environment}-price-fetcher"
  description   = "Fetches price data from multiple providers"

  role    = var.execution_role_arn
  handler = "lambda_handler.handler"
  runtime = "python3.13"

  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  timeout     = 900 # 15 minutes
  memory_size = var.price_fetcher_memory_size

  # Prevent concurrent invocations from competing for API quotas
  reserved_concurrent_executions = var.price_fetcher_reserved_concurrency

  environment {
    variables = {
      ENVIRONMENT                 = var.environment
      AWS_REGION_NAME             = var.aws_region
      DATA_SOURCE                 = var.data_source
      STALENESS_THRESHOLD_MINUTES = tostring(var.staleness_threshold_minutes)
      MAX_SYMBOLS_PER_RUN         = tostring(var.max_symbols_per_run)
      PRICE_FETCHER_SECRET_NAME = var.config_secret_name
      # DynamoDB table names
      PRICES_TABLE      = var.prices_table
      CONFIG_TABLE_NAME = var.config_table
      WATCHLIST_TABLE   = var.watchlist_table
    }
  }

  depends_on = [aws_cloudwatch_log_group.price_fetcher]

  tags = {
    Environment = var.environment
    Module      = "lambda"
    Function    = "price-fetcher"
  }

  lifecycle {
    ignore_changes = [
      filename,
      source_code_hash,
    ]
  }
}

# Holiday Fetcher
resource "aws_lambda_function" "holiday_fetcher" {
  function_name = "${var.environment}-price-fetcher-holidays"
  description   = "Updates market holiday calendar"

  role    = var.execution_role_arn
  handler = "lambda_handler.holiday_handler"
  runtime = "python3.13"

  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  timeout     = 300 # 5 minutes
  memory_size = 256

  environment {
    variables = {
      ENVIRONMENT               = var.environment
      AWS_REGION_NAME           = var.aws_region
      CONFIG_TABLE_NAME         = var.config_table
      PRICES_TABLE              = var.prices_table
      PRICE_FETCHER_SECRET_NAME = var.config_secret_name
    }
  }

  depends_on = [aws_cloudwatch_log_group.holiday_fetcher]

  tags = {
    Environment = var.environment
    Module      = "lambda"
    Function    = "holiday-fetcher"
  }

  lifecycle {
    ignore_changes = [
      filename,
      source_code_hash,
    ]
  }
}

# Price Validator
resource "aws_lambda_function" "validator" {
  function_name = "${var.environment}-price-fetcher-validator"
  description   = "Validates price data completeness"

  role    = var.execution_role_arn
  handler = "lambda_handler.validator_handler"
  runtime = "python3.13"

  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  timeout     = 600 # 10 minutes
  memory_size = 512

  environment {
    variables = {
      ENVIRONMENT     = var.environment
      AWS_REGION_NAME = var.aws_region
      PRICES_TABLE    = var.prices_table
    }
  }

  depends_on = [aws_cloudwatch_log_group.validator]

  tags = {
    Environment = var.environment
    Module      = "lambda"
    Function    = "validator"
  }

  lifecycle {
    ignore_changes = [
      filename,
      source_code_hash,
    ]
  }
}
