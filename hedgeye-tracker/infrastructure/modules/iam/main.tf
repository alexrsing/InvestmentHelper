# IAM Module - Main Configuration
#
# This module creates an IAM execution role for the Hedgeye Risk Tracker application
# with least-privilege policies for DynamoDB, Secrets Manager, and CloudWatch Logs

# IAM Role for application execution
# Trust policy allows Lambda service to assume this role
resource "aws_iam_role" "execution_role" {
  name        = "${var.environment}-hedgeye-risk-tracker-execution-role"
  description = "Execution role for Hedgeye Risk Tracker ${var.environment} environment"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name        = "${var.environment}-hedgeye-risk-tracker-execution-role"
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "hedgeye-risk-tracker"
    }
  )
}

# DynamoDB Access Policy
# Grants read/write permissions to environment-specific tables only
resource "aws_iam_role_policy" "dynamodb_access" {
  name = "dynamodb-access"
  role = aws_iam_role.execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBTableAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchWriteItem",
          "dynamodb:BatchGetItem"
        ]
        Resource = [
          var.trade_ranges_table_arn,
          var.trend_ranges_table_arn
        ]
      },
      {
        Sid    = "SharedETFTableAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/${var.price_table_name}",
          "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/${var.etf_history_table_name}"
        ]
      }
    ]
  })
}

# Secrets Manager Access Policy
# Grants read-only access to Gmail service account secret
resource "aws_iam_role_policy" "secrets_manager_access" {
  name = "secrets-manager-access"
  role = aws_iam_role.execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsManagerReadAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = var.gmail_secret_arn
      }
    ]
  })
}

# CloudWatch Logs Policy
# Grants permissions to create log groups, streams, and write logs
resource "aws_iam_role_policy" "cloudwatch_logs_access" {
  name = "cloudwatch-logs-access"
  role = aws_iam_role.execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/aws/lambda/${var.environment}-hedgeye-risk-tracker:*"
        ]
      }
    ]
  })
}
