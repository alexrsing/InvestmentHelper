# Scheduler Module Outputs

output "price_fetcher_rule_arn" {
  description = "ARN of the price fetcher EventBridge rule"
  value       = var.price_fetcher_enabled ? aws_cloudwatch_event_rule.price_fetcher[0].arn : null
}

output "price_fetcher_rule_name" {
  description = "Name of the price fetcher EventBridge rule"
  value       = var.price_fetcher_enabled ? aws_cloudwatch_event_rule.price_fetcher[0].name : null
}

output "holiday_fetcher_rule_arn" {
  description = "ARN of the holiday fetcher EventBridge rule"
  value       = var.holiday_fetcher_enabled ? aws_cloudwatch_event_rule.holiday_fetcher[0].arn : null
}

output "holiday_fetcher_rule_name" {
  description = "Name of the holiday fetcher EventBridge rule"
  value       = var.holiday_fetcher_enabled ? aws_cloudwatch_event_rule.holiday_fetcher[0].name : null
}

output "validator_rule_arn" {
  description = "ARN of the validator EventBridge rule"
  value       = var.validator_enabled ? aws_cloudwatch_event_rule.validator[0].arn : null
}

output "validator_rule_name" {
  description = "Name of the validator EventBridge rule"
  value       = var.validator_enabled ? aws_cloudwatch_event_rule.validator[0].name : null
}

output "all_rule_arns" {
  description = "List of all enabled EventBridge rule ARNs"
  value = compact([
    var.price_fetcher_enabled ? aws_cloudwatch_event_rule.price_fetcher[0].arn : "",
    var.holiday_fetcher_enabled ? aws_cloudwatch_event_rule.holiday_fetcher[0].arn : "",
    var.validator_enabled ? aws_cloudwatch_event_rule.validator[0].arn : "",
  ])
}
