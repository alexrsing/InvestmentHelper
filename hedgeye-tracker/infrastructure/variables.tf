# Terraform Variables for DynamoDB Tables
#
# These variables allow environment-specific configurations
# Values are provided via .tfvars files in environments/ directory

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
  default     = "us-east-1"
}

variable "table_name_prefix" {
  description = "Prefix for table names to support multiple environments"
  type        = string
  default     = ""
}

variable "enable_point_in_time_recovery" {
  description = "Enable point-in-time recovery for tables"
  type        = bool
  default     = true
}

variable "enable_deletion_protection" {
  description = "Enable deletion protection (recommended for production)"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "secret_recovery_window_days" {
  description = "Number of days to retain secrets after deletion (7-30)"
  type        = number
  default     = 30
}

variable "enable_secret_rotation" {
  description = "Enable automatic secret rotation"
  type        = bool
  default     = false
}

# Lambda Configuration
variable "enable_lambda" {
  description = "Enable Lambda function deployment"
  type        = bool
  default     = false
}

variable "lambda_deployment_package" {
  description = "Path to the Lambda deployment package (zip file)"
  type        = string
  default     = null
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds (max 900)"
  type        = number
  default     = 900
}

variable "lambda_memory_size" {
  description = "Lambda function memory allocation in MB"
  type        = number
  default     = 512
}

variable "lambda_log_retention_days" {
  description = "CloudWatch Logs retention period for Lambda"
  type        = number
  default     = 30
}

variable "gmail_user_email" {
  description = "Gmail address to impersonate for domain-wide delegation"
  type        = string
  default     = ""
}

# Scheduler Configuration
variable "enable_scheduler" {
  description = "Enable EventBridge scheduler (requires enable_lambda = true)"
  type        = bool
  default     = false
}

variable "schedule_expression" {
  description = "Cron or rate expression for scheduled execution"
  type        = string
  default     = "cron(0 8 ? * MON-FRI *)" # 8 AM UTC weekdays
}

variable "scheduler_enabled" {
  description = "Whether the scheduler rule is active (can be disabled without deleting)"
  type        = bool
  default     = true
}

# Monitoring Configuration
variable "enable_monitoring" {
  description = "Enable CloudWatch alarms and SNS topics (requires enable_lambda = true)"
  type        = bool
  default     = false
}

variable "monitoring_alert_email" {
  description = "Email address for monitoring alert notifications (leave empty to skip)"
  type        = string
  default     = ""
}

# GitHub OIDC Configuration
variable "enable_github_oidc" {
  description = "Enable GitHub Actions OIDC authentication for CI/CD"
  type        = bool
  default     = false
}

variable "github_repository" {
  description = "GitHub repository in format 'owner/repo' for OIDC trust policy"
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

# Google Chat Notifications
variable "enable_google_chat_notifications" {
  description = "Enable Google Chat notifications for CloudWatch alarms"
  type        = bool
  default     = false
}
