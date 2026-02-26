# Staging Environment Configuration

environment = "staging"
aws_region  = "us-west-2"

# Use environment prefix for table names
table_name_prefix = "staging-"

# Enable point-in-time recovery
enable_point_in_time_recovery = true

# Deletion protection enabled for staging
enable_deletion_protection = true

# Additional tags
tags = {
  CostCenter = "staging"
  Owner      = "engineering-team"
}

# Lambda Configuration
enable_lambda             = false
lambda_timeout            = 900
lambda_memory_size        = 512
lambda_log_retention_days = 60
gmail_user_email          = "" # Configure before enabling Lambda

# Scheduler Configuration
enable_scheduler    = false
schedule_expression = "cron(0 8 * * ? *)" # Daily at 8 AM UTC
scheduler_enabled   = true

# Monitoring Configuration
enable_monitoring      = false
monitoring_alert_email = "" # Configure before enabling monitoring

# GitHub OIDC Configuration
enable_github_oidc     = false
github_repository      = "sing-email/hedgeye-risk-ranges-tracker"
terraform_state_bucket = "hedgeye-risk-tracker-terraform-state"
terraform_lock_table   = "terraform-locks"
