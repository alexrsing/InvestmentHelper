# Google Chat Notifier Module
#
# Creates a Lambda function that forwards CloudWatch alarm notifications
# from SNS to Google Chat via webhook.

locals {
  function_name = "${var.environment}-google-chat-notifier"
}

# Archive the Lambda source code
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/src"
  output_path = "${path.module}/lambda.zip"
}

# IAM Role for Lambda
resource "aws_iam_role" "notifier" {
  name = local.function_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# CloudWatch Logs policy
resource "aws_iam_role_policy" "logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.notifier.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${local.function_name}:*"
      }
    ]
  })
}

# Secrets Manager policy
resource "aws_iam_role_policy" "secrets" {
  name = "secrets-manager"
  role = aws_iam_role.notifier.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = var.webhook_secret_arn
      }
    ]
  })
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# Lambda Function
resource "aws_lambda_function" "notifier" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = local.function_name
  role             = aws_iam_role.notifier.arn
  handler          = "handler.handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.13"
  timeout          = 30
  memory_size      = 128

  environment {
    variables = {
      WEBHOOK_SECRET_NAME = var.webhook_secret_name
      AWS_REGION_NAME     = var.aws_region
    }
  }

  tags = var.tags
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "notifier" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# SNS Topic for alarm notifications
resource "aws_sns_topic" "alarms" {
  name = "${var.environment}-cloudwatch-alarms"

  tags = var.tags
}

# Lambda permission to allow SNS to invoke
resource "aws_lambda_permission" "sns" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.notifier.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.alarms.arn
}

# SNS Subscription to Lambda
resource "aws_sns_topic_subscription" "lambda" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.notifier.arn
}
