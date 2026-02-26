# Secrets Manager Module - Input Variables
#
# Variables required to configure Secrets Manager secrets

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "recovery_window_days" {
  description = "Number of days to retain secret after deletion (7-30 days)"
  type        = number
  default     = 30
  validation {
    condition     = var.recovery_window_days >= 7 && var.recovery_window_days <= 30
    error_message = "Recovery window must be between 7 and 30 days."
  }
}

variable "enable_rotation" {
  description = "Enable automatic secret rotation"
  type        = bool
  default     = false
}

variable "rotation_days" {
  description = "Number of days between automatic rotations"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Common tags to apply to all secrets"
  type        = map(string)
  default     = {}
}
