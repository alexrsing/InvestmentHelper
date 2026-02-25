# Scheduler Module Variables

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

# Schedule expressions (cron or rate)
# Market hours: 9:30 AM - 4:00 PM ET = 14:30 - 21:00 UTC
variable "price_fetcher_schedule" {
  description = "Cron expression for price fetcher (default: every 15 min during market hours)"
  type        = string
  default     = "cron(*/15 14-21 ? * MON-FRI *)"
}

variable "holiday_fetcher_schedule" {
  description = "Cron expression for holiday fetcher (default: weekly on Sunday)"
  type        = string
  default     = "cron(0 8 ? * SUN *)"
}

variable "validator_schedule" {
  description = "Cron expression for validator (default: daily at market close)"
  type        = string
  default     = "cron(0 21 ? * MON-FRI *)"
}

# Lambda function references
variable "price_fetcher_function_arn" {
  description = "ARN of the price fetcher Lambda function"
  type        = string
}

variable "price_fetcher_function_name" {
  description = "Name of the price fetcher Lambda function"
  type        = string
}

variable "holiday_fetcher_function_arn" {
  description = "ARN of the holiday fetcher Lambda function"
  type        = string
}

variable "holiday_fetcher_function_name" {
  description = "Name of the holiday fetcher Lambda function"
  type        = string
}

variable "validator_function_arn" {
  description = "ARN of the validator Lambda function"
  type        = string
}

variable "validator_function_name" {
  description = "Name of the validator Lambda function"
  type        = string
}

# Enable/disable individual schedules
variable "price_fetcher_enabled" {
  description = "Enable price fetcher schedule"
  type        = bool
  default     = true
}

variable "holiday_fetcher_enabled" {
  description = "Enable holiday fetcher schedule"
  type        = bool
  default     = true
}

variable "validator_enabled" {
  description = "Enable validator schedule"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
