# Development Environment Configuration

environment = "dev"
aws_region  = "us-east-1"

# Use environment prefix for table names
table_name_prefix = "dev-"

# Enable point-in-time recovery
enable_point_in_time_recovery = true

# Deletion protection disabled for dev (can recreate easily)
enable_deletion_protection = false

# Additional tags
tags = {
  CostCenter = "development"
  Owner      = "engineering-team"
}

# Lambda Configuration
enable_lambda              = true
lambda_deployment_package  = "../deployment/lambda.zip"
lambda_timeout             = 900 # 15 minutes max
lambda_memory_size         = 512
lambda_log_retention_days  = 30
gmail_user_email           = "shared@singtech.com.au"

# Scheduler Configuration
# Requires enable_lambda = true to take effect
enable_scheduler    = true
schedule_expression = "cron(0/15 13-14 ? * * *)" # Every 15 min, 5-7 AM PST (13:00-14:45 UTC) daily
scheduler_enabled   = true

# Monitoring Configuration
enable_monitoring      = true
monitoring_alert_email = "" # Set to receive alert notifications

# GitHub OIDC Configuration
# Enables GitHub Actions to deploy without AWS credentials
enable_github_oidc     = true
github_repository      = "sing-email/hedgeye-risk-ranges-tracker"
terraform_state_bucket = "hedgeye-risk-tracker-terraform-state"
terraform_lock_table   = "terraform-locks"

# Google Chat Notifications
# Enables CloudWatch alarm notifications to Google Chat
enable_google_chat_notifications = true

# To enable full deployment:
# 1. Run: ./deployment/package-lambda.sh
# 2. Set: enable_lambda = true
# 3. Set: lambda_deployment_package = "../deployment/lambda.zip"
# 4. Set: enable_scheduler = true (optional)
# 5. Set: enable_monitoring = true (optional)
# 6. Run: terraform apply
