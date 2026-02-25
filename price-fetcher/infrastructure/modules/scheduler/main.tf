# Scheduler Module - EventBridge Rules
# Creates scheduled execution rules for Lambda functions

# =============================================================================
# Price Fetcher Schedule (during market hours)
# =============================================================================

resource "aws_cloudwatch_event_rule" "price_fetcher" {
  count = var.price_fetcher_enabled ? 1 : 0

  name                = "${var.environment}-price-fetcher-schedule"
  description         = "Trigger price fetcher during market hours"
  schedule_expression = var.price_fetcher_schedule

  tags = merge(var.tags, {
    Environment = var.environment
    Module      = "scheduler"
    Function    = "price-fetcher"
  })
}

resource "aws_cloudwatch_event_target" "price_fetcher" {
  count = var.price_fetcher_enabled ? 1 : 0

  rule      = aws_cloudwatch_event_rule.price_fetcher[0].name
  target_id = "price-fetcher-lambda"
  arn       = var.price_fetcher_function_arn
}

resource "aws_lambda_permission" "price_fetcher" {
  count = var.price_fetcher_enabled ? 1 : 0

  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.price_fetcher_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.price_fetcher[0].arn
}

# =============================================================================
# Holiday Fetcher Schedule (weekly)
# =============================================================================

resource "aws_cloudwatch_event_rule" "holiday_fetcher" {
  count = var.holiday_fetcher_enabled ? 1 : 0

  name                = "${var.environment}-price-fetcher-holidays-schedule"
  description         = "Trigger holiday fetcher weekly"
  schedule_expression = var.holiday_fetcher_schedule

  tags = merge(var.tags, {
    Environment = var.environment
    Module      = "scheduler"
    Function    = "holiday-fetcher"
  })
}

resource "aws_cloudwatch_event_target" "holiday_fetcher" {
  count = var.holiday_fetcher_enabled ? 1 : 0

  rule      = aws_cloudwatch_event_rule.holiday_fetcher[0].name
  target_id = "holiday-fetcher-lambda"
  arn       = var.holiday_fetcher_function_arn
}

resource "aws_lambda_permission" "holiday_fetcher" {
  count = var.holiday_fetcher_enabled ? 1 : 0

  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.holiday_fetcher_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.holiday_fetcher[0].arn
}

# =============================================================================
# Validator Schedule (daily at market close)
# =============================================================================

resource "aws_cloudwatch_event_rule" "validator" {
  count = var.validator_enabled ? 1 : 0

  name                = "${var.environment}-price-fetcher-validator-schedule"
  description         = "Trigger validator daily at market close"
  schedule_expression = var.validator_schedule

  tags = merge(var.tags, {
    Environment = var.environment
    Module      = "scheduler"
    Function    = "validator"
  })
}

resource "aws_cloudwatch_event_target" "validator" {
  count = var.validator_enabled ? 1 : 0

  rule      = aws_cloudwatch_event_rule.validator[0].name
  target_id = "validator-lambda"
  arn       = var.validator_function_arn
}

resource "aws_lambda_permission" "validator" {
  count = var.validator_enabled ? 1 : 0

  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.validator_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.validator[0].arn
}
