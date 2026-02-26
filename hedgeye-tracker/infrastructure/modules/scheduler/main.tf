# Scheduler Module - Main Configuration
#
# Creates EventBridge rule for scheduled Lambda invocation

# EventBridge Rule for scheduled execution
resource "aws_cloudwatch_event_rule" "schedule" {
  name                = var.rule_name
  description         = var.description
  schedule_expression = var.schedule_expression
  state               = var.enabled ? "ENABLED" : "DISABLED"

  tags = var.tags
}

# EventBridge Target - Lambda function
resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.schedule.name
  target_id = "LambdaTarget"
  arn       = var.lambda_function_arn

  # Optional input payload to pass to Lambda
  input = var.event_input != null ? var.event_input : jsonencode({
    source      = "aws.events"
    rule_name   = var.rule_name
    environment = var.environment
  })
}

# Permission for EventBridge to invoke Lambda
resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridgeInvoke-${var.rule_name}"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.schedule.arn
}
