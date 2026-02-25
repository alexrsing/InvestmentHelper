# Terraform Outputs for Price Fetcher Infrastructure
#
# These outputs provide information about deployed resources.

# =============================================================================
# Lambda Outputs
# =============================================================================

output "lambda_functions" {
  description = "Map of Lambda function names and ARNs"
  value = var.enable_lambda ? {
    price_fetcher = {
      name = module.lambda[0].price_fetcher_name
      arn  = module.lambda[0].price_fetcher_arn
    }
    holiday_fetcher = {
      name = module.lambda[0].holiday_fetcher_name
      arn  = module.lambda[0].holiday_fetcher_arn
    }
    validator = {
      name = module.lambda[0].validator_name
      arn  = module.lambda[0].validator_arn
    }
  } : {}
}

output "price_fetcher_function_name" {
  description = "Name of the price fetcher Lambda function"
  value       = var.enable_lambda ? module.lambda[0].price_fetcher_name : ""
}

output "price_fetcher_log_group" {
  description = "CloudWatch log group for price fetcher"
  value       = var.enable_lambda ? module.lambda[0].price_fetcher_log_group_name : ""
}

# =============================================================================
# Secrets Outputs
# =============================================================================

output "config_secret_name" {
  description = "Name of the price fetcher config secret (for manual API key configuration)"
  value       = module.secrets.config_secret_name
}

# =============================================================================
# IAM Outputs
# =============================================================================

output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = module.iam.execution_role_arn
}

# =============================================================================
# Scheduler Outputs
# =============================================================================

output "scheduler_rules" {
  description = "Map of EventBridge rule names"
  value = var.enable_lambda && var.enable_scheduler ? {
    price_fetcher   = module.scheduler[0].price_fetcher_rule_name
    holiday_fetcher = module.scheduler[0].holiday_fetcher_rule_name
    validator       = module.scheduler[0].validator_rule_name
  } : {}
}

# =============================================================================
# Monitoring Outputs
# =============================================================================

output "monitoring_topics" {
  description = "Map of SNS topic ARNs for alerts"
  value = var.enable_lambda && var.enable_monitoring ? {
    critical = module.monitoring[0].critical_topic_arn
    warning  = module.monitoring[0].warning_topic_arn
  } : {}
}

# =============================================================================
# GitHub OIDC Outputs
# =============================================================================

output "github_actions_role_arn" {
  description = "ARN of the IAM role for GitHub Actions"
  value       = var.enable_github_oidc && local.state_bucket_arn != "" ? module.github_oidc[0].github_actions_role_arn : ""
}

# =============================================================================
# General Outputs
# =============================================================================

output "environment" {
  description = "Current environment name"
  value       = var.environment
}

output "aws_region" {
  description = "AWS region where resources are deployed"
  value       = var.aws_region
}

output "aws_account_id" {
  description = "AWS account ID"
  value       = data.aws_caller_identity.current.account_id
}
