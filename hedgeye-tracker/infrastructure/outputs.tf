# Terraform Outputs
#
# These outputs provide information about created resources

output "trade_ranges_table_name" {
  description = "Name of the trade ranges DynamoDB table"
  value       = aws_dynamodb_table.trade_ranges.name
}

output "trade_ranges_table_arn" {
  description = "ARN of the trade ranges DynamoDB table"
  value       = aws_dynamodb_table.trade_ranges.arn
}

output "trend_ranges_table_name" {
  description = "Name of the trend ranges DynamoDB table"
  value       = aws_dynamodb_table.trend_ranges.name
}

output "trend_ranges_table_arn" {
  description = "ARN of the trend ranges DynamoDB table"
  value       = aws_dynamodb_table.trend_ranges.arn
}

output "environment" {
  description = "Current environment"
  value       = var.environment
}

output "table_summary" {
  description = "Summary of created tables"
  value = {
    environment = var.environment
    region      = var.aws_region
    tables = {
      trade_ranges = {
        name = aws_dynamodb_table.trade_ranges.name
        arn  = aws_dynamodb_table.trade_ranges.arn
      }
      trend_ranges = {
        name = aws_dynamodb_table.trend_ranges.name
        arn  = aws_dynamodb_table.trend_ranges.arn
      }
    }
  }
}

# IAM Role Outputs
output "execution_role_arn" {
  description = "ARN of the IAM execution role for Lambda function"
  value       = module.iam.execution_role_arn
}

output "execution_role_name" {
  description = "Name of the IAM execution role"
  value       = module.iam.execution_role_name
}

# Secrets Manager Outputs
output "gmail_secret_arn" {
  description = "ARN of the Gmail service account secret"
  value       = module.secrets.gmail_secret_arn
}

output "gmail_secret_name" {
  description = "Name of the Gmail service account secret"
  value       = module.secrets.gmail_secret_name
}

# Lambda Outputs (conditional)
output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = var.enable_lambda ? module.lambda[0].function_arn : null
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = var.enable_lambda ? module.lambda[0].function_name : null
}

output "lambda_log_group_name" {
  description = "CloudWatch Log Group name for Lambda"
  value       = var.enable_lambda ? module.lambda[0].log_group_name : null
}

# Scheduler Outputs (conditional)
output "scheduler_rule_arn" {
  description = "ARN of the EventBridge scheduler rule"
  value       = var.enable_lambda && var.enable_scheduler ? module.scheduler[0].rule_arn : null
}

output "scheduler_rule_name" {
  description = "Name of the EventBridge scheduler rule"
  value       = var.enable_lambda && var.enable_scheduler ? module.scheduler[0].rule_name : null
}

output "schedule_expression" {
  description = "Schedule expression for the EventBridge rule"
  value       = var.enable_lambda && var.enable_scheduler ? module.scheduler[0].schedule_expression : null
}

# Monitoring Outputs (conditional)
output "critical_alerts_topic_arn" {
  description = "ARN of the SNS topic for critical alerts"
  value       = var.enable_lambda && var.enable_monitoring ? module.monitoring[0].critical_alerts_topic_arn : null
}

output "warning_alerts_topic_arn" {
  description = "ARN of the SNS topic for warning alerts"
  value       = var.enable_lambda && var.enable_monitoring ? module.monitoring[0].warning_alerts_topic_arn : null
}

output "monitoring_alarm_summary" {
  description = "Summary of CloudWatch alarms created"
  value       = var.enable_lambda && var.enable_monitoring ? module.monitoring[0].alarm_summary : null
}

# GitHub OIDC Outputs (conditional)
output "github_actions_role_arn" {
  description = "ARN of the IAM role for GitHub Actions"
  value       = var.enable_github_oidc ? module.github_oidc[0].role_arn : null
}

output "github_actions_role_name" {
  description = "Name of the IAM role for GitHub Actions"
  value       = var.enable_github_oidc ? module.github_oidc[0].role_name : null
}

output "github_oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC provider"
  value       = var.enable_github_oidc ? module.github_oidc[0].oidc_provider_arn : null
}

# Google Chat Notifier Outputs (conditional)
output "google_chat_webhook_secret_name" {
  description = "Name of the Secrets Manager secret for Google Chat webhook"
  value       = var.enable_google_chat_notifications ? aws_secretsmanager_secret.google_chat_webhook[0].name : null
}

output "google_chat_notifier_sns_topic_arn" {
  description = "ARN of the SNS topic for CloudWatch alarms to Google Chat"
  value       = var.enable_google_chat_notifications ? module.google_chat_notifier[0].sns_topic_arn : null
}
