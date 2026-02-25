# GitHub OIDC Module Variables

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "aws_account_id" {
  description = "AWS account ID"
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "AWS account ID must be a 12-digit number."
  }
}

variable "github_org" {
  description = "GitHub organization name"
  type        = string
  default     = "sing-email"
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "price-fetcher"
}

variable "create_oidc_provider" {
  description = "Create OIDC provider (set to false if it already exists in account)"
  type        = bool
  default     = true
}

variable "state_bucket_arn" {
  description = "ARN of the S3 bucket for Terraform state"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:s3:::", var.state_bucket_arn))
    error_message = "Must be a valid S3 bucket ARN."
  }
}

variable "state_lock_table_arn" {
  description = "ARN of the DynamoDB table for state locking"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:dynamodb:", var.state_lock_table_arn))
    error_message = "Must be a valid DynamoDB table ARN."
  }
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
