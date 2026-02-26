# Scheduler Module - Variables
#
# Configuration options for EventBridge scheduling

variable "rule_name" {
  description = "Name of the EventBridge rule"
  type        = string
}

variable "description" {
  description = "Description of the scheduled rule"
  type        = string
  default     = "Scheduled execution of Hedgeye Risk Ranges Tracker"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "schedule_expression" {
  description = "Cron or rate expression for the schedule"
  type        = string

  validation {
    condition     = can(regex("^(cron|rate)\\(", var.schedule_expression))
    error_message = "Schedule expression must start with 'cron(' or 'rate('."
  }
}

variable "enabled" {
  description = "Enable or disable the scheduled rule"
  type        = bool
  default     = true
}

variable "lambda_function_arn" {
  description = "ARN of the Lambda function to invoke"
  type        = string
}

variable "lambda_function_name" {
  description = "Name of the Lambda function to invoke"
  type        = string
}

variable "event_input" {
  description = "Optional JSON input payload to pass to Lambda"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
