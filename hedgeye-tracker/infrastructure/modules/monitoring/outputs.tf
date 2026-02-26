# Monitoring Module - Outputs
#
# Exports monitoring resource details

output "critical_alerts_topic_arn" {
  description = "ARN of the SNS topic for critical alerts"
  value       = aws_sns_topic.critical_alerts.arn
}

output "warning_alerts_topic_arn" {
  description = "ARN of the SNS topic for warning alerts"
  value       = aws_sns_topic.warning_alerts.arn
}

output "lambda_errors_alarm_arn" {
  description = "ARN of the Lambda errors alarm"
  value       = aws_cloudwatch_metric_alarm.lambda_errors.arn
}

output "lambda_throttles_alarm_arn" {
  description = "ARN of the Lambda throttles alarm"
  value       = aws_cloudwatch_metric_alarm.lambda_throttles.arn
}

output "auth_errors_alarm_arn" {
  description = "ARN of the authentication errors alarm"
  value       = aws_cloudwatch_metric_alarm.auth_errors.arn
}

output "dynamodb_errors_alarm_arn" {
  description = "ARN of the DynamoDB errors alarm"
  value       = aws_cloudwatch_metric_alarm.dynamodb_errors.arn
}

output "alarm_summary" {
  description = "Summary of all alarms created"
  value = {
    critical_alarms = [
      aws_cloudwatch_metric_alarm.lambda_errors.alarm_name,
      aws_cloudwatch_metric_alarm.lambda_throttles.alarm_name,
      aws_cloudwatch_metric_alarm.auth_errors.alarm_name,
      aws_cloudwatch_metric_alarm.dynamodb_errors.alarm_name,
    ]
    warning_alarms = concat(
      [aws_cloudwatch_metric_alarm.lambda_duration_warning.alarm_name],
      var.enable_no_invocation_alarm ? [aws_cloudwatch_metric_alarm.no_invocations[0].alarm_name] : []
    )
    sns_topics = {
      critical = aws_sns_topic.critical_alerts.name
      warning  = aws_sns_topic.warning_alerts.name
    }
  }
}
