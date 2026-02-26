# Production Environment Configuration

environment = "prod"
aws_region  = "us-east-1"

# Use environment prefix for table names
table_name_prefix = "prod-"

# Enable point-in-time recovery (REQUIRED for production)
enable_point_in_time_recovery = true

# Deletion protection enabled for production (REQUIRED)
enable_deletion_protection = true

# Additional tags
tags = {
  CostCenter  = "production"
  Owner       = "engineering-team"
  Criticality = "high"
}

# Lambda Configuration
enable_lambda             = false
lambda_timeout            = 900
lambda_memory_size        = 1024 # More memory for production
lambda_log_retention_days = 90   # Longer retention for production
gmail_user_email          = ""   # Configure before enabling Lambda

# Scheduler Configuration
enable_scheduler    = false
schedule_expression = "cron(0 8 ? * MON-FRI *)" # 8 AM UTC weekdays
scheduler_enabled   = true

# Monitoring Configuration (RECOMMENDED for production)
enable_monitoring      = false # Enable after Lambda deployment
monitoring_alert_email = ""    # Configure for alert notifications

# GitHub OIDC Configuration
enable_github_oidc     = false
github_repository      = "sing-email/hedgeye-risk-ranges-tracker"
terraform_state_bucket = "hedgeye-risk-tracker-terraform-state"
terraform_lock_table   = "terraform-locks"
