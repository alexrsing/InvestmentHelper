# Terraform Variables for Price Fetcher Infrastructure
#
# These variables allow environment-specific configurations.
# Values are provided via .tfvars files in environments/ directory.

# =============================================================================
# Core Configuration
# =============================================================================

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-west-2"
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# =============================================================================
# Feature Flags
# =============================================================================

variable "enable_lambda" {
  description = "Enable Lambda function deployment"
  type        = bool
  default     = true
}

variable "enable_scheduler" {
  description = "Enable EventBridge scheduled execution (requires enable_lambda = true)"
  type        = bool
  default     = false
}

variable "enable_monitoring" {
  description = "Enable CloudWatch alarms and SNS topics (requires enable_lambda = true)"
  type        = bool
  default     = false
}

variable "enable_github_oidc" {
  description = "Enable GitHub Actions OIDC authentication for CI/CD"
  type        = bool
  default     = true
}

variable "enable_deletion_protection" {
  description = "Enable deletion protection for critical resources"
  type        = bool
  default     = false
}

variable "enable_dynamodb_pitr" {
  description = "Enable point-in-time recovery for DynamoDB tables"
  type        = bool
  default     = true
}

# =============================================================================
# DynamoDB Table Creation
# =============================================================================

variable "create_prices_table" {
  description = "Create the prices table (set false if table exists externally)"
  type        = bool
  default     = false
}

variable "create_config_table" {
  description = "Create the config table (set false if table exists externally)"
  type        = bool
  default     = false
}

# =============================================================================
# API Provider Configuration
# =============================================================================

variable "data_source" {
  description = "Data source preference (auto, alphavantage, twelvedata, finnhub, fmp, yfinance)"
  type        = string
  default     = "auto"
}

# =============================================================================
# Lambda Configuration
# =============================================================================

variable "lambda_memory_size" {
  description = "Lambda function memory allocation in MB"
  type        = number
  default     = 512

  validation {
    condition     = var.lambda_memory_size >= 128 && var.lambda_memory_size <= 10240
    error_message = "Lambda memory size must be between 128 and 10240 MB."
  }
}

variable "lambda_log_retention_days" {
  description = "CloudWatch Logs retention period for Lambda"
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.lambda_log_retention_days)
    error_message = "Log retention must be a valid CloudWatch retention value."
  }
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

# =============================================================================
# Scheduler Configuration
# =============================================================================

variable "scheduler_enabled" {
  description = "Whether scheduler rules are active (can be disabled without deleting)"
  type        = bool
  default     = true
}

variable "price_fetcher_schedule" {
  description = "Cron expression for price fetcher (UTC). Default: every 15 min during US market hours"
  type        = string
  default     = "cron(*/15 14-21 ? * MON-FRI *)"
}

variable "holiday_fetcher_schedule" {
  description = "Cron expression for holiday fetcher (UTC). Default: Sunday at 8 AM UTC"
  type        = string
  default     = "cron(0 8 ? * SUN *)"
}

variable "validator_schedule" {
  description = "Cron expression for validator (UTC). Default: weekdays at 9 PM UTC (after market close)"
  type        = string
  default     = "cron(0 21 ? * MON-FRI *)"
}

# =============================================================================
# Monitoring Configuration
# =============================================================================

variable "monitoring_alert_email" {
  description = "Email address for monitoring alert notifications (leave empty to skip)"
  type        = string
  default     = ""
}

# =============================================================================
# Secrets Configuration
# =============================================================================

variable "secret_recovery_window_days" {
  description = "Number of days to retain secrets after deletion (7-30, 0 for immediate)"
  type        = number
  default     = 30

  validation {
    condition     = var.secret_recovery_window_days == 0 || (var.secret_recovery_window_days >= 7 && var.secret_recovery_window_days <= 30)
    error_message = "Recovery window must be 0 (immediate deletion) or between 7 and 30 days."
  }
}

# =============================================================================
# GitHub OIDC Configuration
# =============================================================================

variable "github_org" {
  description = "GitHub organization name"
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repository name (without org prefix)"
  type        = string
  default     = ""
}

variable "terraform_state_bucket" {
  description = "S3 bucket name for Terraform state (used in GitHub Actions policy)"
  type        = string
  default     = ""
}

variable "terraform_lock_table" {
  description = "DynamoDB table name for Terraform state locking"
  type        = string
  default     = ""
}
