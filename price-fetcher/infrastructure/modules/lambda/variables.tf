# Lambda Module Variables

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_region" {
  description = "AWS region for Lambda functions"
  type        = string
  default     = "us-west-2"
}

variable "execution_role_arn" {
  description = "ARN of the IAM execution role for Lambda"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:iam::", var.execution_role_arn))
    error_message = "Must be a valid IAM role ARN."
  }
}

# Memory configuration
variable "price_fetcher_memory_size" {
  description = "Memory size for price fetcher Lambda (MB)"
  type        = number
  default     = 512

  validation {
    condition     = var.price_fetcher_memory_size >= 128 && var.price_fetcher_memory_size <= 10240
    error_message = "Memory size must be between 128 and 10240 MB."
  }
}

# Logging configuration
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention must be a valid CloudWatch retention value."
  }
}

# Application configuration
variable "data_source" {
  description = "Data source preference (auto, alphavantage, twelvedata, finnhub, fmp, yfinance)"
  type        = string
  default     = "auto"
}

variable "staleness_threshold_minutes" {
  description = "Minutes before price data is considered stale"
  type        = number
  default     = 15
}

variable "max_symbols_per_run" {
  description = "Maximum symbols to process per Lambda invocation"
  type        = number
  default     = 50
}

# Secret name (from secrets module)
variable "config_secret_name" {
  description = "Name of the price fetcher config secret (JSON)"
  type        = string
  default     = ""
}

# DynamoDB table names
variable "prices_table" {
  description = "DynamoDB table name for price data"
  type        = string
  default     = ""
}

variable "config_table" {
  description = "DynamoDB table name for configuration"
  type        = string
  default     = ""
}

variable "watchlist_table" {
  description = "DynamoDB table name for watchlist (symbols to track)"
  type        = string
  default     = ""
}

# Concurrency configuration
variable "price_fetcher_reserved_concurrency" {
  description = "Reserved concurrent executions for price fetcher Lambda. Set to 1 to prevent API quota competition."
  type        = number
  default     = 1

  validation {
    condition     = var.price_fetcher_reserved_concurrency >= 1 && var.price_fetcher_reserved_concurrency <= 1000
    error_message = "Reserved concurrency must be between 1 and 1000."
  }
}

