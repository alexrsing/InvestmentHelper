# Monitoring Module - Variables
#
# Configuration options for CloudWatch monitoring

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "lambda_function_name" {
  description = "Name of the Lambda function to monitor"
  type        = string
}

variable "lambda_log_group_name" {
  description = "Name of the Lambda CloudWatch Log Group"
  type        = string
}

variable "lambda_timeout_ms" {
  description = "Lambda function timeout in milliseconds (for duration alarms)"
  type        = number
  default     = 900000 # 15 minutes
}

variable "alert_email" {
  description = "Email address for alarm notifications (leave empty to skip email subscription)"
  type        = string
  default     = ""
}

variable "enable_no_invocation_alarm" {
  description = "Enable alarm for missing scheduled invocations"
  type        = bool
  default     = true
}

variable "expected_invocations_period_hours" {
  description = "Expected number of hours between invocations (for no-invocation alarm)"
  type        = number
  default     = 24 # Daily execution expected
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
