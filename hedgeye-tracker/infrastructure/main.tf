# Main Terraform Configuration for Hedgeye Risk Tracker Infrastructure
#
# This configuration manages DynamoDB tables for ETF monitoring data

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

# Local values for table naming
locals {
  # Use prefix if provided, otherwise use environment
  table_prefix = var.table_name_prefix != "" ? var.table_name_prefix : "${var.environment}-"

  # Table names (flat names, no environment prefix — aligned with InvestmentHelper convention)
  trade_ranges_table_name = "hedgeye_daily_ranges"
  trend_ranges_table_name = "hedgeye_weekly_ranges"

  # Common tags for all resources
  common_tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "hedgeye-risk-tracker"
    },
    var.tags
  )
}

# DynamoDB Table: Trade Ranges
# Stores buy/sell trade levels for ETF symbols
resource "aws_dynamodb_table" "trade_ranges" {
  name         = local.trade_ranges_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "etf_symbol"

  deletion_protection_enabled = var.enable_deletion_protection

  attribute {
    name = "etf_symbol"
    type = "S"
  }

  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  tags = merge(
    local.common_tags,
    {
      Name        = local.trade_ranges_table_name
      TableType   = "trade-ranges"
      Description = "ETF monitoring trade ranges for buy and sell levels"
    }
  )
}

# DynamoDB Table: Trend Ranges
# Stores trend range data for ETF symbols
resource "aws_dynamodb_table" "trend_ranges" {
  name         = local.trend_ranges_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "etf_symbol"

  deletion_protection_enabled = var.enable_deletion_protection

  attribute {
    name = "etf_symbol"
    type = "S"
  }

  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  tags = merge(
    local.common_tags,
    {
      Name        = local.trend_ranges_table_name
      TableType   = "trend-ranges"
      Description = "ETF monitoring trend ranges"
    }
  )
}

# Secrets Manager Module
# Creates secrets for storing sensitive credentials
module "secrets" {
  source = "./modules/secrets"

  environment          = var.environment
  recovery_window_days = var.secret_recovery_window_days
  enable_rotation      = var.enable_secret_rotation

  tags = local.common_tags
}

# IAM Module
# Creates execution role with policies for DynamoDB, Secrets Manager, and CloudWatch Logs
module "iam" {
  source = "./modules/iam"

  environment    = var.environment
  aws_region     = var.aws_region
  aws_account_id = data.aws_caller_identity.current.account_id

  # DynamoDB table ARNs
  trade_ranges_table_arn = aws_dynamodb_table.trade_ranges.arn
  trend_ranges_table_arn = aws_dynamodb_table.trend_ranges.arn

  # Secrets Manager ARN from secrets module
  gmail_secret_arn = module.secrets.gmail_secret_arn

  tags = local.common_tags
}

# Lambda Module
# Creates Lambda function for running the application
# Note: Requires deployment package to be created first
module "lambda" {
  source = "./modules/lambda"
  count  = var.enable_lambda ? 1 : 0

  function_name      = "${var.environment}-hedgeye-risk-tracker"
  description        = "Hedgeye Risk Ranges Tracker - fetches trading data from email and stores in DynamoDB"
  execution_role_arn = module.iam.execution_role_arn

  # Deployment package - set via variable or deploy separately
  deployment_package_path = var.lambda_deployment_package

  # Runtime configuration
  runtime     = "python3.13"
  handler     = "lambda_handler.handler"
  timeout     = var.lambda_timeout
  memory_size = var.lambda_memory_size

  # Environment variables for the application
  # Note: AWS_REGION is reserved by Lambda, use AWS_REGION_NAME instead
  environment_variables = {
    AWS_REGION_NAME    = var.aws_region
    GMAIL_USER_EMAIL   = var.gmail_user_email
    GMAIL_SECRET_NAME  = module.secrets.gmail_secret_name
    PRICE_TABLE_NAME   = "etfs"
    TRADE_RANGES_TABLE = local.trade_ranges_table_name
    TREND_RANGES_TABLE = local.trend_ranges_table_name
  }

  # CloudWatch Logs configuration
  log_retention_days = var.lambda_log_retention_days

  # EventBridge integration (permission handled by scheduler module)
  allow_eventbridge_invocation = false
  eventbridge_rule_arn         = null

  tags = local.common_tags
}

# Scheduler Module
# Creates EventBridge rule for scheduled Lambda invocation
# Only created when both Lambda and scheduler are enabled
module "scheduler" {
  source = "./modules/scheduler"
  count  = var.enable_lambda && var.enable_scheduler ? 1 : 0

  rule_name   = "${var.environment}-hedgeye-daily-schedule"
  environment = var.environment
  description = "Scheduled execution of Hedgeye Risk Ranges Tracker - ${var.environment}"

  # Schedule configuration
  schedule_expression = var.schedule_expression
  enabled             = var.scheduler_enabled

  # Lambda function to invoke
  lambda_function_arn  = module.lambda[0].function_arn
  lambda_function_name = module.lambda[0].function_name

  tags = local.common_tags
}

# Monitoring Module
# Creates CloudWatch alarms and SNS topics for application monitoring
# Only created when Lambda is enabled
module "monitoring" {
  source = "./modules/monitoring"
  count  = var.enable_lambda && var.enable_monitoring ? 1 : 0

  environment           = var.environment
  lambda_function_name  = module.lambda[0].function_name
  lambda_log_group_name = module.lambda[0].log_group_name
  lambda_timeout_ms     = var.lambda_timeout * 1000 # Convert seconds to milliseconds

  # Alert notifications
  alert_email = var.monitoring_alert_email

  # No-invocation alarm - alerts if Lambda doesn't run for 24 hours
  enable_no_invocation_alarm        = var.enable_scheduler
  expected_invocations_period_hours = 24

  tags = local.common_tags
}

# GitHub OIDC Module
# Creates OIDC provider and IAM role for GitHub Actions deployments
# Only created when explicitly enabled
module "github_oidc" {
  source = "./modules/github-oidc"
  count  = var.enable_github_oidc ? 1 : 0

  environment    = var.environment
  aws_region     = var.aws_region
  aws_account_id = data.aws_caller_identity.current.account_id

  github_repository      = var.github_repository
  terraform_state_bucket = var.terraform_state_bucket
  terraform_lock_table   = var.terraform_lock_table

  tags = local.common_tags
}

# Google Chat Webhook Secret
# Stores the Google Chat webhook URL for notifications
resource "aws_secretsmanager_secret" "google_chat_webhook" {
  count = var.enable_google_chat_notifications ? 1 : 0

  name        = "${var.environment}/hedgeye/google-chat-webhook"
  description = "Google Chat webhook URL for CloudWatch alarm notifications"

  tags = local.common_tags
}

# Google Chat Notifier Module
# Creates Lambda function to forward CloudWatch alarms to Google Chat
module "google_chat_notifier" {
  source = "./modules/google-chat-notifier"
  count  = var.enable_google_chat_notifications ? 1 : 0

  environment         = var.environment
  aws_region          = var.aws_region
  webhook_secret_name = aws_secretsmanager_secret.google_chat_webhook[0].name
  webhook_secret_arn  = aws_secretsmanager_secret.google_chat_webhook[0].arn
  log_retention_days  = var.lambda_log_retention_days

  tags = local.common_tags
}

# Connect Monitoring SNS Topics to Google Chat Notifier
# When both monitoring and Google Chat notifications are enabled,
# subscribe the monitoring topics to the Google Chat notifier Lambda

# Critical alerts -> Google Chat
resource "aws_sns_topic_subscription" "critical_to_google_chat" {
  count = var.enable_lambda && var.enable_monitoring && var.enable_google_chat_notifications ? 1 : 0

  topic_arn = module.monitoring[0].critical_alerts_topic_arn
  protocol  = "lambda"
  endpoint  = module.google_chat_notifier[0].function_arn
}

# Warning alerts -> Google Chat
resource "aws_sns_topic_subscription" "warning_to_google_chat" {
  count = var.enable_lambda && var.enable_monitoring && var.enable_google_chat_notifications ? 1 : 0

  topic_arn = module.monitoring[0].warning_alerts_topic_arn
  protocol  = "lambda"
  endpoint  = module.google_chat_notifier[0].function_arn
}

# Lambda permission for monitoring critical alerts to invoke Google Chat notifier
resource "aws_lambda_permission" "critical_alerts_invoke" {
  count = var.enable_lambda && var.enable_monitoring && var.enable_google_chat_notifications ? 1 : 0

  statement_id  = "AllowCriticalAlertsSNS"
  action        = "lambda:InvokeFunction"
  function_name = module.google_chat_notifier[0].function_name
  principal     = "sns.amazonaws.com"
  source_arn    = module.monitoring[0].critical_alerts_topic_arn
}

# Lambda permission for monitoring warning alerts to invoke Google Chat notifier
resource "aws_lambda_permission" "warning_alerts_invoke" {
  count = var.enable_lambda && var.enable_monitoring && var.enable_google_chat_notifications ? 1 : 0

  statement_id  = "AllowWarningAlertsSNS"
  action        = "lambda:InvokeFunction"
  function_name = module.google_chat_notifier[0].function_name
  principal     = "sns.amazonaws.com"
  source_arn    = module.monitoring[0].warning_alerts_topic_arn
}
