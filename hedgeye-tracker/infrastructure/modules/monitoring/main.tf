# Monitoring Module - Main Configuration
#
# Creates CloudWatch alarms and SNS topics for application monitoring

# SNS Topic for critical alerts
resource "aws_sns_topic" "critical_alerts" {
  name = "${var.environment}-hedgeye-alerts-critical"

  tags = var.tags
}

# SNS Topic for warning alerts
resource "aws_sns_topic" "warning_alerts" {
  name = "${var.environment}-hedgeye-alerts-warning"

  tags = var.tags
}

# Email subscription for critical alerts (if email provided)
resource "aws_sns_topic_subscription" "critical_email" {
  count = var.alert_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.critical_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Email subscription for warning alerts (if email provided)
resource "aws_sns_topic_subscription" "warning_email" {
  count = var.alert_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.warning_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ==============================================================================
# CRITICAL ALARMS
# ==============================================================================

# Alarm: Lambda Execution Errors
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.environment}-hedgeye-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Lambda function encountered errors"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.critical_alerts.arn]

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  treat_missing_data = "notBreaching"

  tags = var.tags
}

# Alarm: Lambda Throttling
resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${var.environment}-hedgeye-lambda-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Lambda function was throttled"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.critical_alerts.arn]

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  treat_missing_data = "notBreaching"

  tags = var.tags
}

# ==============================================================================
# WARNING ALARMS
# ==============================================================================

# Alarm: Lambda Duration Warning (approaching timeout)
resource "aws_cloudwatch_metric_alarm" "lambda_duration_warning" {
  alarm_name          = "${var.environment}-hedgeye-lambda-duration-warning"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300 # 5 minutes
  statistic           = "Maximum"
  threshold           = var.lambda_timeout_ms * 0.8 # 80% of timeout
  alarm_description   = "Lambda function duration approaching timeout limit"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.warning_alerts.arn]

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  treat_missing_data = "notBreaching"

  tags = var.tags
}

# Alarm: No Invocations (schedule may be broken)
resource "aws_cloudwatch_metric_alarm" "no_invocations" {
  count = var.enable_no_invocation_alarm ? 1 : 0

  alarm_name          = "${var.environment}-hedgeye-no-invocations"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = var.expected_invocations_period_hours
  metric_name         = "Invocations"
  namespace           = "AWS/Lambda"
  period              = 3600 # 1 hour
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "No Lambda invocations in expected period - scheduler may be broken"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.warning_alerts.arn]

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  treat_missing_data = "breaching"

  tags = var.tags
}

# ==============================================================================
# CLOUDWATCH LOG METRIC FILTERS
# ==============================================================================

# Metric filter for authentication errors in logs
resource "aws_cloudwatch_log_metric_filter" "auth_errors" {
  name           = "${var.environment}-hedgeye-auth-errors"
  pattern        = "?\"Authentication error\" ?\"authentication failed\" ?\"credential refresh failed\""
  log_group_name = var.lambda_log_group_name

  metric_transformation {
    name          = "AuthenticationErrors"
    namespace     = "Hedgeye/${var.environment}"
    value         = "1"
    default_value = "0"
  }
}

# Alarm for authentication errors
resource "aws_cloudwatch_metric_alarm" "auth_errors" {
  alarm_name          = "${var.environment}-hedgeye-auth-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "AuthenticationErrors"
  namespace           = "Hedgeye/${var.environment}"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Gmail or AWS authentication errors detected"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.critical_alerts.arn]

  treat_missing_data = "notBreaching"

  tags = var.tags
}

# Metric filter for DynamoDB errors in logs
resource "aws_cloudwatch_log_metric_filter" "dynamodb_errors" {
  name           = "${var.environment}-hedgeye-dynamodb-errors"
  pattern        = "?\"Error putting item\" ?\"Error batch putting\" ?\"Error getting item\" ?\"DynamoDB error\" ?\"AccessDeniedException\" ?\"ClientError\""
  log_group_name = var.lambda_log_group_name

  metric_transformation {
    name          = "DynamoDBErrors"
    namespace     = "Hedgeye/${var.environment}"
    value         = "1"
    default_value = "0"
  }
}

# Alarm for DynamoDB errors
resource "aws_cloudwatch_metric_alarm" "dynamodb_errors" {
  alarm_name          = "${var.environment}-hedgeye-dynamodb-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "DynamoDBErrors"
  namespace           = "Hedgeye/${var.environment}"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = 5 # Allow a few transient errors
  alarm_description   = "Multiple DynamoDB errors detected"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.critical_alerts.arn]

  treat_missing_data = "notBreaching"

  tags = var.tags
}
