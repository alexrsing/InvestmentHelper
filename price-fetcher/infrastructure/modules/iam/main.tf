# IAM Module - Lambda Execution Role
# Creates least-privilege IAM role for price-fetcher Lambda functions

locals {
  # Construct log group ARNs from function names
  log_group_arns = [
    for name in var.lambda_function_names :
    "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/aws/lambda/${name}"
  ]

  # DynamoDB table ARNs for price fetcher (flat table names matching InvestmentHelper)
  dynamodb_table_arn_patterns = [
    "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/etfs",
    "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/etf_history",
    "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/watchlist",
    "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/price_fetcher_config",
  ]
}

# Lambda Execution Role
resource "aws_iam_role" "lambda_execution" {
  name = "${var.environment}-price-fetcher-execution-role"

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

  tags = merge(var.tags, {
    Environment = var.environment
    Module      = "iam"
  })
}

# DynamoDB Access Policy
# Allows access to environment-prefixed tables and additional specified tables
resource "aws_iam_role_policy" "dynamodb_access" {
  name = "${var.environment}-price-fetcher-dynamodb-access"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      {
        Sid    = "DynamoDBTableAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchWriteItem",
          "dynamodb:BatchGetItem"
        ]
        Resource = local.dynamodb_table_arn_patterns
      },
      {
        Sid    = "DynamoDBIndexAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [for pattern in local.dynamodb_table_arn_patterns : "${pattern}/index/*"]
      }
    ],
    length(var.additional_dynamodb_table_arns) > 0 ? [
      {
        Sid    = "AdditionalDynamoDBTableAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchWriteItem",
          "dynamodb:BatchGetItem"
        ]
        Resource = var.additional_dynamodb_table_arns
      }
    ] : [])
  })
}

# Secrets Manager Access Policy
resource "aws_iam_role_policy" "secrets_access" {
  count = var.enable_secrets_access ? 1 : 0

  name = "${var.environment}-price-fetcher-secrets-access"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsManagerAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = var.secret_arns
      }
    ]
  })
}

# CloudWatch Logs Policy
resource "aws_iam_role_policy" "cloudwatch_logs" {
  count = length(var.lambda_function_names) > 0 ? 1 : 0

  name = "${var.environment}-price-fetcher-cloudwatch-logs"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [for arn in local.log_group_arns : "${arn}:*"]
      }
    ]
  })
}
