# Monitoring Module Outputs

output "critical_topic_arn" {
  description = "ARN of the critical alerts SNS topic"
  value       = aws_sns_topic.critical.arn
}

output "critical_topic_name" {
  description = "Name of the critical alerts SNS topic"
  value       = aws_sns_topic.critical.name
}

output "warning_topic_arn" {
  description = "ARN of the warning alerts SNS topic"
  value       = aws_sns_topic.warning.arn
}

output "warning_topic_name" {
  description = "Name of the warning alerts SNS topic"
  value       = aws_sns_topic.warning.name
}

output "error_alarm_arns" {
  description = "Map of Lambda error alarm ARNs"
  value       = { for k, v in aws_cloudwatch_metric_alarm.lambda_errors : k => v.arn }
}

output "throttle_alarm_arns" {
  description = "Map of Lambda throttle alarm ARNs"
  value       = { for k, v in aws_cloudwatch_metric_alarm.lambda_throttles : k => v.arn }
}

output "duration_alarm_arns" {
  description = "Map of Lambda duration alarm ARNs"
  value       = { for k, v in aws_cloudwatch_metric_alarm.lambda_duration : k => v.arn }
}
