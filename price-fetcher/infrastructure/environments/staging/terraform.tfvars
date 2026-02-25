# Staging Environment Configuration
# Deploy: terraform apply -var-file=environments/staging/terraform.tfvars

environment = "staging"
aws_region  = "us-east-2"

# =============================================================================
# Feature Flags
# =============================================================================

# Enable all components for testing
enable_lambda      = true
enable_scheduler   = true
enable_monitoring  = true
enable_github_oidc = true

# Protect staging data
enable_deletion_protection    = true
enable_dynamodb_pitr = true

# Create DynamoDB tables (new region, no existing tables)
create_prices_table = true
create_config_table = true

# =============================================================================
# API Provider Configuration
# =============================================================================

data_source = "fmp"

# =============================================================================
# Lambda Configuration
# =============================================================================

lambda_memory_size        = 512
lambda_log_retention_days = 60 # Longer retention for debugging

# Application settings
staleness_threshold_minutes = 15
max_symbols_per_run         = 50

# =============================================================================
# Scheduler Configuration
# =============================================================================

# Same schedules as dev for testing
price_fetcher_schedule   = "cron(*/15 14-21 ? * MON-FRI *)"
holiday_fetcher_schedule = "cron(0 8 ? * SUN *)"
validator_schedule       = "cron(0 21 ? * MON-FRI *)"

scheduler_enabled = true

# =============================================================================
# Monitoring Configuration
# =============================================================================

monitoring_alert_email = "" # Set to receive alert notifications

# =============================================================================
# Secrets Configuration
# =============================================================================

secret_recovery_window_days = 30

# =============================================================================
# GitHub OIDC Configuration
# =============================================================================

github_org             = "sing-email"
github_repo            = "price-fetcher"
terraform_state_bucket = "price-fetcher-terraform-state"
terraform_lock_table   = "price-fetcher-terraform-lock"

# =============================================================================
# Additional Tags
# =============================================================================

tags = {
  CostCenter = "staging"
  Owner      = "engineering-team"
}
