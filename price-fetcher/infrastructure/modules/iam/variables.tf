# IAM Module Variables

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_region" {
  description = "AWS region for resource ARN construction"
  type        = string
  default     = "us-west-2"
}

variable "aws_account_id" {
  description = "AWS account ID for resource ARN construction"
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "AWS account ID must be a 12-digit number."
  }
}

variable "secret_arns" {
  description = "List of Secrets Manager secret ARNs the Lambda can access"
  type        = list(string)
  default     = []
}

variable "enable_secrets_access" {
  description = "Whether to create the secrets access policy (workaround for count depending on unknown values)"
  type        = bool
  default     = true
}

variable "lambda_function_names" {
  description = "List of Lambda function names for CloudWatch Logs permissions"
  type        = list(string)
  default     = []
}

variable "additional_dynamodb_table_arns" {
  description = "Additional DynamoDB table ARNs the Lambda can access (for legacy tables without environment prefix)"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
