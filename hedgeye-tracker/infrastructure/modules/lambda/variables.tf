# Lambda Module - Variables
#
# Configuration options for the Lambda function

variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "description" {
  description = "Description of the Lambda function"
  type        = string
  default     = "Hedgeye Risk Ranges Tracker - fetches and processes trading data"
}

variable "execution_role_arn" {
  description = "ARN of the IAM role for Lambda execution"
  type        = string
}

variable "handler" {
  description = "Lambda function handler (file.function)"
  type        = string
  default     = "lambda_handler.handler"
}

variable "runtime" {
  description = "Lambda runtime environment"
  type        = string
  default     = "python3.13"
}

variable "timeout" {
  description = "Lambda function timeout in seconds (max 900)"
  type        = number
  default     = 900 # 15 minutes - max allowed

  validation {
    condition     = var.timeout > 0 && var.timeout <= 900
    error_message = "Lambda timeout must be between 1 and 900 seconds."
  }
}

variable "memory_size" {
  description = "Lambda function memory allocation in MB"
  type        = number
  default     = 512

  validation {
    condition     = var.memory_size >= 128 && var.memory_size <= 10240
    error_message = "Lambda memory must be between 128 and 10240 MB."
  }
}

variable "deployment_package_path" {
  description = "Path to the Lambda deployment package (zip file)"
  type        = string
  default     = null
}

variable "environment_variables" {
  description = "Environment variables for the Lambda function"
  type        = map(string)
  default     = {}
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention period in days"
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653, 0], var.log_retention_days)
    error_message = "Log retention must be a valid CloudWatch Logs retention value."
  }
}

variable "enable_function_url" {
  description = "Enable Lambda function URL for direct HTTP access"
  type        = bool
  default     = false
}

variable "allow_eventbridge_invocation" {
  description = "Allow EventBridge to invoke this Lambda function"
  type        = bool
  default     = true
}

variable "eventbridge_rule_arn" {
  description = "ARN of the EventBridge rule that will invoke this function"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
