# Google Chat Notifier Module Variables

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "webhook_secret_name" {
  description = "Name of the Secrets Manager secret containing the Google Chat webhook URL"
  type        = string
}

variable "webhook_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the Google Chat webhook URL"
  type        = string
}

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
