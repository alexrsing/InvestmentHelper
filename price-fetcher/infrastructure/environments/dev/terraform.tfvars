# Development Environment Configuration
# Deploy: terraform apply -var-file=environments/dev/terraform.tfvars

environment = "dev"
aws_region  = "us-west-2"

# =============================================================================
# Feature Flags
# =============================================================================

# Enable all components for development
enable_lambda      = true
enable_scheduler   = true
enable_monitoring  = true
enable_github_oidc = true

# Dev can be recreated easily
enable_deletion_protection    = false
enable_dynamodb_pitr = true

# =============================================================================
# API Provider Configuration
# =============================================================================

# Auto-select best available source
data_source = "fmp"

# =============================================================================
# Lambda Configuration
# =============================================================================

lambda_memory_size        = 512
lambda_log_retention_days = 30

# Application settings
staleness_threshold_minutes = 15
max_symbols_per_run         = 50

# =============================================================================
# Scheduler Configuration
# =============================================================================

# Every 15 minutes during US market hours (9:30 AM - 4:00 PM EST = 14:30-21:00 UTC)
price_fetcher_schedule = "cron(*/15 14-21 ? * MON-FRI *)"

# Weekly on Sunday at 8 AM UTC
holiday_fetcher_schedule = "cron(0 8 ? * SUN *)"

# Daily at 9 PM UTC (after market close)
validator_schedule = "cron(0 21 ? * MON-FRI *)"

scheduler_enabled = false  # Disabled to conserve FMP API quota

# =============================================================================
# Monitoring Configuration
# =============================================================================

monitoring_alert_email = "" # Set to receive alert notifications

# =============================================================================
# Secrets Configuration
# =============================================================================

secret_recovery_window_days = 7 # Shorter recovery for dev

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
  CostCenter = "development"
  Owner      = "engineering-team"
}

# =============================================================================
# Deployment Instructions
# =============================================================================
# 1. Bootstrap infrastructure (if not done):
#    cd infrastructure/bootstrap
#    terraform init && terraform apply
#
# 2. Initialize main infrastructure:
#    cd infrastructure
#    terraform init -backend-config=environments/dev/backend-config.hcl
#
# 3. Deploy:
#    terraform plan -var-file=environments/dev/terraform.tfvars
#    terraform apply -var-file=environments/dev/terraform.tfvars
#
# 4. Configure API keys in Secrets Manager (single JSON secret):
#    aws secretsmanager put-secret-value --secret-id dev/price-fetcher/config \
#      --secret-string '{"ALPHA_VANTAGE_API_KEY":"...","ALPHA_VANTAGE_TIER":"free","TWELVEDATA_API_KEY":"...","TWELVEDATA_TIER":"free","FINNHUB_API_KEY":"...","FINNHUB_TIER":"free","FMP_API_KEY":"...","FMP_TIER":"free"}'
#
# 5. Package and deploy Lambda code:
#    ./deployment/package-lambda.sh
#    aws lambda update-function-code --function-name dev-price-fetcher --zip-file fileb://deployment/build/lambda.zip
