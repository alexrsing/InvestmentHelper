# Production Environment Configuration
# Deploy: terraform apply -var-file=environments/prod/terraform.tfvars
#
# WARNING: Production environment. Review changes carefully before applying.

environment = "prod"
aws_region  = "us-east-1"

# =============================================================================
# Feature Flags
# =============================================================================

# Start with Lambda enabled, scheduler and monitoring disabled
# Enable progressively after verification:
# 1. Deploy Lambda and verify it works with test invocations
# 2. Enable scheduler once Lambda is verified
# 3. Enable monitoring once scheduler is active
enable_lambda      = true
enable_scheduler   = true
enable_monitoring  = true
enable_github_oidc = true

# REQUIRED for production - protect against accidental deletion
enable_deletion_protection    = true
enable_dynamodb_pitr = true

# DynamoDB table creation
create_prices_table = true
create_config_table = true

# =============================================================================
# API Provider Configuration
# =============================================================================

data_source = "fmp"

# =============================================================================
# Lambda Configuration
# =============================================================================

# More memory for production workloads
lambda_memory_size        = 1024
lambda_log_retention_days = 90 # Longer retention for compliance

# Application settings
staleness_threshold_minutes = 15
max_symbols_per_run         = 100 # Higher limit for production

# =============================================================================
# Scheduler Configuration
# =============================================================================

# More frequent fetching in production (every 5 minutes)
price_fetcher_schedule   = "cron(*/5 14-21 ? * MON-FRI *)"
holiday_fetcher_schedule = "cron(0 8 ? * SUN *)"
validator_schedule       = "cron(0 21 ? * MON-FRI *)"

scheduler_enabled = false  # Disabled to conserve FMP API quota

# =============================================================================
# Monitoring Configuration
# =============================================================================

monitoring_alert_email = "shared@sing.email"

# =============================================================================
# Secrets Configuration
# =============================================================================

# Maximum recovery window for production
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
  CostCenter  = "production"
  Owner       = "engineering-team"
  Criticality = "high"
}

# =============================================================================
# Production Deployment Checklist
# =============================================================================
# Before enabling scheduler and monitoring:
#
# [ ] 1. Infrastructure deployed successfully
# [ ] 2. API keys configured in Secrets Manager
# [ ] 3. Lambda test invocation successful:
#        aws lambda invoke --function-name prod-price-fetcher \
#          --payload '{"dry_run": true}' response.json
# [ ] 4. Real data fetch test:
#        aws lambda invoke --function-name prod-price-fetcher \
#          --payload '{"symbols": ["AAPL"], "max_symbols": 1}' response.json
# [ ] 5. Enable scheduler: set enable_scheduler = true
# [ ] 6. Verify scheduled execution in CloudWatch Logs
# [ ] 7. Configure monitoring_alert_email
# [ ] 8. Enable monitoring: set enable_monitoring = true
# [ ] 9. Verify alarms are functioning
