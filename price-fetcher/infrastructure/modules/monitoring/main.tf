# Monitoring Module - CloudWatch Alarms and SNS Topics
# Creates alarms for Lambda errors, throttles, and duration warnings

# =============================================================================
# SNS Topics for Alerts
# =============================================================================

resource "aws_sns_topic" "critical" {
  name = "${var.environment}-price-fetcher-alerts-critical"

  tags = {
    Environment = var.environment
    Module      = "monitoring"
    Severity    = "critical"
  }
}

resource "aws_sns_topic" "warning" {
  name = "${var.environment}-price-fetcher-alerts-warning"

  tags = {
    Environment = var.environment
    Module      = "monitoring"
    Severity    = "warning"
  }
}

# =============================================================================
# Lambda Error Alarms (Critical)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = var.enable_monitoring ? var.lambda_function_names : {}

  alarm_name          = "${var.environment}-${each.key}-errors"
  alarm_description   = "Lambda function ${each.key} has errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = each.value
  }

  alarm_actions = [aws_sns_topic.critical.arn]
  ok_actions    = [aws_sns_topic.critical.arn]

  tags = {
    Environment = var.environment
    Module      = "monitoring"
    Function    = each.key
    Severity    = "critical"
  }
}

# =============================================================================
# Lambda Throttle Alarms (Critical)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  for_each = var.enable_monitoring ? var.lambda_function_names : {}

  alarm_name          = "${var.environment}-${each.key}-throttles"
  alarm_description   = "Lambda function ${each.key} is being throttled"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = each.value
  }

  alarm_actions = [aws_sns_topic.critical.arn]
  ok_actions    = [aws_sns_topic.critical.arn]

  tags = {
    Environment = var.environment
    Module      = "monitoring"
    Function    = each.key
    Severity    = "critical"
  }
}

# =============================================================================
# Lambda Duration Alarms (Warning - >80% of timeout)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  for_each = var.enable_monitoring ? var.lambda_function_timeouts : {}

  alarm_name          = "${var.environment}-${each.key}-duration-warning"
  alarm_description   = "Lambda function ${each.key} duration exceeds 80% of timeout"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Maximum"
  threshold           = each.value * 1000 * 0.8 # 80% of timeout in milliseconds
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.lambda_function_names[each.key]
  }

  alarm_actions = [aws_sns_topic.warning.arn]
  ok_actions    = [aws_sns_topic.warning.arn]

  tags = {
    Environment = var.environment
    Module      = "monitoring"
    Function    = each.key
    Severity    = "warning"
  }
}

# =============================================================================
# No Invocations Alarm (Warning - detect if scheduler stopped)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "no_invocations" {
  count = var.enable_monitoring ? 1 : 0

  alarm_name          = "${var.environment}-price-fetcher-no-invocations"
  alarm_description   = "Price fetcher has not been invoked in 24 hours"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Invocations"
  namespace           = "AWS/Lambda"
  period              = 86400 # 24 hours
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "breaching"

  dimensions = {
    FunctionName = var.lambda_function_names["price_fetcher"]
  }

  alarm_actions = [aws_sns_topic.warning.arn]
  ok_actions    = [aws_sns_topic.warning.arn]

  tags = {
    Environment = var.environment
    Module      = "monitoring"
    Severity    = "warning"
  }
}
