# IAM Module - Input Variables
#
# Variables required to configure the IAM execution role

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_region" {
  description = "AWS region where resources are deployed"
  type        = string
}

variable "aws_account_id" {
  description = "AWS account ID for resource ARN construction"
  type        = string
}

variable "trade_ranges_table_arn" {
  description = "ARN of the trade ranges DynamoDB table"
  type        = string
}

variable "trend_ranges_table_arn" {
  description = "ARN of the trend ranges DynamoDB table"
  type        = string
}

variable "gmail_secret_arn" {
  description = "ARN of the Gmail service account secret in Secrets Manager"
  type        = string
}

variable "price_table_name" {
  description = "Name of the shared ETFs DynamoDB table (for price lookups and updates)"
  type        = string
  default     = "etfs"
}

variable "etf_history_table_name" {
  description = "Name of the shared ETF history DynamoDB table"
  type        = string
  default     = "etf_history"
}

variable "tags" {
  description = "Common tags to apply to all IAM resources"
  type        = map(string)
  default     = {}
}
