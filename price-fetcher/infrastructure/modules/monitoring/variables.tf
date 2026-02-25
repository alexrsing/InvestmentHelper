# Monitoring Module Variables

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "enable_monitoring" {
  description = "Enable CloudWatch alarms"
  type        = bool
  default     = true
}

variable "lambda_function_names" {
  description = "Map of Lambda function keys to names"
  type        = map(string)

  # Expected format:
  # {
  #   price_fetcher   = "dev-price-fetcher"
  #   holiday_fetcher = "dev-price-fetcher-holidays"
  #   validator       = "dev-price-fetcher-validator"
  # }
}

variable "lambda_function_timeouts" {
  description = "Map of Lambda function keys to timeout in seconds (for duration alarms)"
  type        = map(number)
  default = {
    price_fetcher   = 900
    holiday_fetcher = 300
    validator       = 600
  }
}
