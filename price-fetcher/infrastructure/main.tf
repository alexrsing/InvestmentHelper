# Main Terraform Configuration for Price Fetcher Infrastructure
#
# This configuration orchestrates all modules for the Lambda-based price fetching system.
# Deploy using environment-specific tfvars:
#   terraform init -backend-config=environments/<env>/backend-config.hcl
#   terraform plan -var-file=environments/<env>/terraform.tfvars
#   terraform apply -var-file=environments/<env>/terraform.tfvars

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend configuration is in backend.tf
  # Run: terraform init -backend-config=environments/<env>/backend-config.hcl
}

provider "aws" {
  region = var.aws_region
}

# Data source to get current AWS account ID
data "aws_caller_identity" "current" {}

# Local values for common configuration
locals {
  # Common tags for all resources
  common_tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "price-fetcher"
    },
    var.tags
  )

  # Lambda function names
  price_fetcher_name   = "${var.environment}-price-fetcher"
  holiday_fetcher_name = "${var.environment}-price-fetcher-holidays"
  validator_name       = "${var.environment}-price-fetcher-validator"

  # State bucket and table ARNs (constructed from names)
  # Note: State infrastructure is always in us-west-2 (bootstrap region)
  state_bucket_arn = var.terraform_state_bucket != "" ? "arn:aws:s3:::${var.terraform_state_bucket}" : ""
  state_lock_arn   = var.terraform_lock_table != "" ? "arn:aws:dynamodb:us-west-2:${data.aws_caller_identity.current.account_id}:table/${var.terraform_lock_table}" : ""
}

# =============================================================================
# Secrets Module
# Creates Secrets Manager secrets for API keys
# =============================================================================

module "secrets" {
  source = "./modules/secrets"

  environment          = var.environment
  recovery_window_days = var.secret_recovery_window_days

  tags = local.common_tags
}

# =============================================================================
# IAM Module
# Creates execution role with least-privilege policies
# =============================================================================

module "iam" {
  source = "./modules/iam"

  environment    = var.environment
  aws_region     = var.aws_region
  aws_account_id = data.aws_caller_identity.current.account_id

  # Secret ARNs for IAM policy
  secret_arns           = module.secrets.all_secret_arns
  enable_secrets_access = true

  # Lambda function names for log group permissions
  lambda_function_names = [
    local.price_fetcher_name,
    local.holiday_fetcher_name,
    local.validator_name,
  ]

  additional_dynamodb_table_arns = []

  tags = local.common_tags
}

# =============================================================================
# DynamoDB Module
# Creates price fetcher tables (watchlist, optionally prices/config)
# =============================================================================

module "dynamodb" {
  source = "./modules/dynamodb"

  environment = var.environment

  # Watchlist table is always created
  # Prices and config tables may be managed externally during migration
  create_prices_table = var.create_prices_table
  create_config_table = var.create_config_table

  enable_point_in_time_recovery = var.enable_dynamodb_pitr

  tags = local.common_tags
}

# =============================================================================
# Table Names
# Table names passed to Lambda as environment variables
# =============================================================================

locals {
  table_names = {
    prices    = var.create_prices_table ? module.dynamodb.prices_table_name : "etfs"
    config    = var.create_config_table ? module.dynamodb.config_table_name : "price_fetcher_config"
    watchlist = module.dynamodb.watchlist_table_name
  }
}

# =============================================================================
# Lambda Module
# Creates Lambda functions for price fetching, holiday updates, and validation
# =============================================================================

module "lambda" {
  source = "./modules/lambda"
  count  = var.enable_lambda ? 1 : 0

  environment        = var.environment
  aws_region         = var.aws_region
  execution_role_arn = module.iam.execution_role_arn

  # Memory configuration
  price_fetcher_memory_size = var.lambda_memory_size

  # Logging configuration
  log_retention_days = var.lambda_log_retention_days

  # Application configuration
  data_source                 = var.data_source
  staleness_threshold_minutes = var.staleness_threshold_minutes
  max_symbols_per_run         = var.max_symbols_per_run

  # Secret name (single JSON secret)
  config_secret_name = module.secrets.config_secret_name

  # DynamoDB table names
  prices_table    = local.table_names.prices
  config_table    = local.table_names.config
  watchlist_table = local.table_names.watchlist
}

# =============================================================================
# Scheduler Module
# Creates EventBridge rules for scheduled Lambda execution
# =============================================================================

module "scheduler" {
  source = "./modules/scheduler"
  count  = var.enable_lambda && var.enable_scheduler ? 1 : 0

  environment = var.environment

  # Lambda function ARNs to invoke
  price_fetcher_function_arn    = module.lambda[0].price_fetcher_arn
  price_fetcher_function_name   = module.lambda[0].price_fetcher_name
  holiday_fetcher_function_arn  = module.lambda[0].holiday_fetcher_arn
  holiday_fetcher_function_name = module.lambda[0].holiday_fetcher_name
  validator_function_arn        = module.lambda[0].validator_arn
  validator_function_name       = module.lambda[0].validator_name

  # Schedule expressions
  price_fetcher_schedule   = var.price_fetcher_schedule
  holiday_fetcher_schedule = var.holiday_fetcher_schedule
  validator_schedule       = var.validator_schedule

  # Enable/disable individual schedules
  price_fetcher_enabled   = var.scheduler_enabled
  holiday_fetcher_enabled = var.scheduler_enabled
  validator_enabled       = var.scheduler_enabled

  tags = local.common_tags
}

# =============================================================================
# Monitoring Module
# Creates CloudWatch alarms and SNS topics for alerts
# =============================================================================

module "monitoring" {
  source = "./modules/monitoring"
  count  = var.enable_lambda && var.enable_monitoring ? 1 : 0

  environment = var.environment

  # Lambda function names for CloudWatch alarms
  lambda_function_names = {
    price_fetcher   = module.lambda[0].price_fetcher_name
    holiday_fetcher = module.lambda[0].holiday_fetcher_name
    validator       = module.lambda[0].validator_name
  }

  # Timeout values for duration alarms
  lambda_function_timeouts = {
    price_fetcher   = 900
    holiday_fetcher = 300
    validator       = 600
  }
}

# =============================================================================
# GitHub OIDC Module
# Creates OIDC provider and IAM role for GitHub Actions deployments
# =============================================================================

module "github_oidc" {
  source = "./modules/github-oidc"
  count  = var.enable_github_oidc && local.state_bucket_arn != "" ? 1 : 0

  environment    = var.environment
  aws_region     = var.aws_region
  aws_account_id = data.aws_caller_identity.current.account_id

  github_org  = var.github_org
  github_repo = var.github_repo

  # Use existing OIDC provider (shared across all projects in account)
  create_oidc_provider = false

  state_bucket_arn     = local.state_bucket_arn
  state_lock_table_arn = local.state_lock_arn

  tags = local.common_tags
}
