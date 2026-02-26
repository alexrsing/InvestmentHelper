# Lambda Module - Main Configuration
#
# Creates Lambda function for Hedgeye Risk Ranges Tracker application

# CloudWatch Log Group for Lambda function
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# Lambda function
resource "aws_lambda_function" "this" {
  function_name = var.function_name
  description   = var.description
  role          = var.execution_role_arn
  handler       = var.handler
  runtime       = var.runtime
  timeout       = var.timeout
  memory_size   = var.memory_size

  # Use filename for zip deployment or image_uri for container
  filename         = var.deployment_package_path
  source_code_hash = var.deployment_package_path != null ? filebase64sha256(var.deployment_package_path) : null

  environment {
    variables = var.environment_variables
  }

  # Ensure log group exists before function
  depends_on = [aws_cloudwatch_log_group.lambda]

  tags = var.tags
}

# Lambda function URL (optional, for direct HTTP access)
resource "aws_lambda_function_url" "this" {
  count = var.enable_function_url ? 1 : 0

  function_name      = aws_lambda_function.this.function_name
  authorization_type = "AWS_IAM"
}

# Permission for EventBridge to invoke Lambda (will be used by scheduler module)
resource "aws_lambda_permission" "eventbridge" {
  count = var.allow_eventbridge_invocation ? 1 : 0

  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "events.amazonaws.com"
  source_arn    = var.eventbridge_rule_arn
}
