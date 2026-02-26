# Google Chat Notifier Module Outputs

output "function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.notifier.function_name
}

output "function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.notifier.arn
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for CloudWatch alarms"
  value       = aws_sns_topic.alarms.arn
}

output "sns_topic_name" {
  description = "Name of the SNS topic for CloudWatch alarms"
  value       = aws_sns_topic.alarms.name
}
