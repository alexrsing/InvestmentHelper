# Scheduler Module - Outputs
#
# Exports EventBridge rule details

output "rule_arn" {
  description = "ARN of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.schedule.arn
}

output "rule_name" {
  description = "Name of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.schedule.name
}

output "rule_id" {
  description = "ID of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.schedule.id
}

output "schedule_expression" {
  description = "Schedule expression for the rule"
  value       = aws_cloudwatch_event_rule.schedule.schedule_expression
}

output "enabled" {
  description = "Whether the rule is enabled"
  value       = var.enabled
}
