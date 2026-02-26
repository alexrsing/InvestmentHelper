# GitHub Actions OIDC Provider and IAM Role
#
# This module creates the OIDC identity provider and IAM role
# for secure, credential-free GitHub Actions deployments

# OIDC Identity Provider for GitHub Actions
resource "aws_iam_openid_connect_provider" "github_actions" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com",
  ]

  # GitHub's OIDC thumbprint
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd"
  ]

  tags = merge(
    var.tags,
    {
      Name = "GitHubActions-OIDC"
    }
  )
}

# IAM Role for GitHub Actions to assume
resource "aws_iam_role" "github_actions" {
  name = "${var.environment}-github-actions-deployment"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github_actions.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:*"
        }
      }
    }]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-github-actions-deployment"
    }
  )
}

# Policy for Terraform state access (S3 and DynamoDB)
resource "aws_iam_policy" "terraform_state" {
  name        = "${var.environment}-github-actions-terraform-state"
  description = "Allow GitHub Actions to access Terraform state"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3StateAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.terraform_state_bucket}",
          "arn:aws:s3:::${var.terraform_state_bucket}/*"
        ]
      },
      {
        Sid    = "DynamoDBLockAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/${var.terraform_lock_table}"
      }
    ]
  })

  tags = var.tags
}

# Policy for infrastructure management
resource "aws_iam_policy" "infrastructure" {
  name        = "${var.environment}-github-actions-infrastructure"
  description = "Allow GitHub Actions to manage infrastructure resources"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBManagement"
        Effect = "Allow"
        Action = [
          "dynamodb:CreateTable",
          "dynamodb:DeleteTable",
          "dynamodb:DescribeTable",
          "dynamodb:DescribeContinuousBackups",
          "dynamodb:DescribeTimeToLive",
          "dynamodb:ListTagsOfResource",
          "dynamodb:UpdateTable",
          "dynamodb:UpdateContinuousBackups",
          "dynamodb:UpdateTimeToLive",
          "dynamodb:TagResource",
          "dynamodb:UntagResource"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/*hedgeye*"
      },
      {
        Sid    = "SecretsManagerManagement"
        Effect = "Allow"
        Action = [
          "secretsmanager:CreateSecret",
          "secretsmanager:DeleteSecret",
          "secretsmanager:DescribeSecret",
          "secretsmanager:GetSecretValue",
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecret",
          "secretsmanager:TagResource",
          "secretsmanager:UntagResource",
          "secretsmanager:GetResourcePolicy",
          "secretsmanager:PutResourcePolicy",
          "secretsmanager:DeleteResourcePolicy"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${var.aws_account_id}:secret:*hedgeye*"
      },
      {
        Sid    = "IAMRoleManagement"
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:GetRole",
          "iam:UpdateRole",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:ListInstanceProfilesForRole",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:CreatePolicy",
          "iam:DeletePolicy",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
          "iam:ListPolicyVersions",
          "iam:CreatePolicyVersion",
          "iam:DeletePolicyVersion",
          "iam:TagPolicy",
          "iam:UntagPolicy"
        ]
        Resource = [
          "arn:aws:iam::${var.aws_account_id}:role/*hedgeye*",
          "arn:aws:iam::${var.aws_account_id}:policy/*hedgeye*"
        ]
      },
      {
        Sid    = "IAMPassRole"
        Effect = "Allow"
        Action = "iam:PassRole"
        Resource = "arn:aws:iam::${var.aws_account_id}:role/*hedgeye*"
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "lambda.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = var.tags
}

# Policy for Lambda deployment
resource "aws_iam_policy" "lambda_deployment" {
  name        = "${var.environment}-github-actions-lambda-deployment"
  description = "Allow GitHub Actions to deploy Lambda functions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LambdaManagement"
        Effect = "Allow"
        Action = [
          "lambda:CreateFunction",
          "lambda:DeleteFunction",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration",
          "lambda:UpdateFunctionCode",
          "lambda:UpdateFunctionConfiguration",
          "lambda:ListVersionsByFunction",
          "lambda:PublishVersion",
          "lambda:CreateAlias",
          "lambda:DeleteAlias",
          "lambda:GetAlias",
          "lambda:UpdateAlias",
          "lambda:AddPermission",
          "lambda:RemovePermission",
          "lambda:GetPolicy",
          "lambda:TagResource",
          "lambda:UntagResource",
          "lambda:ListTags",
          "lambda:InvokeFunction"
        ]
        Resource = "arn:aws:lambda:${var.aws_region}:${var.aws_account_id}:function:*hedgeye*"
      },
      {
        Sid    = "CloudWatchLogsManagement"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:DeleteLogGroup",
          "logs:DescribeLogGroups",
          "logs:PutRetentionPolicy",
          "logs:DeleteRetentionPolicy",
          "logs:TagLogGroup",
          "logs:UntagLogGroup",
          "logs:ListTagsLogGroup",
          "logs:TagResource",
          "logs:UntagResource",
          "logs:ListTagsForResource"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/aws/lambda/*hedgeye*"
      },
      {
        Sid    = "EventBridgeManagement"
        Effect = "Allow"
        Action = [
          "events:PutRule",
          "events:DeleteRule",
          "events:DescribeRule",
          "events:EnableRule",
          "events:DisableRule",
          "events:PutTargets",
          "events:RemoveTargets",
          "events:ListTargetsByRule",
          "events:TagResource",
          "events:UntagResource",
          "events:ListTagsForResource"
        ]
        Resource = "arn:aws:events:${var.aws_region}:${var.aws_account_id}:rule/*hedgeye*"
      }
    ]
  })

  tags = var.tags
}

# Policy for CloudWatch monitoring
resource "aws_iam_policy" "monitoring" {
  name        = "${var.environment}-github-actions-monitoring"
  description = "Allow GitHub Actions to manage CloudWatch monitoring resources"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SNSManagement"
        Effect = "Allow"
        Action = [
          "sns:CreateTopic",
          "sns:DeleteTopic",
          "sns:GetTopicAttributes",
          "sns:SetTopicAttributes",
          "sns:Subscribe",
          "sns:Unsubscribe",
          "sns:ListSubscriptionsByTopic",
          "sns:TagResource",
          "sns:UntagResource",
          "sns:ListTagsForResource"
        ]
        Resource = "arn:aws:sns:${var.aws_region}:${var.aws_account_id}:*hedgeye*"
      },
      {
        Sid    = "CloudWatchAlarmsManagement"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricAlarm",
          "cloudwatch:DeleteAlarms",
          "cloudwatch:DescribeAlarms",
          "cloudwatch:TagResource",
          "cloudwatch:UntagResource",
          "cloudwatch:ListTagsForResource"
        ]
        Resource = "arn:aws:cloudwatch:${var.aws_region}:${var.aws_account_id}:alarm:*hedgeye*"
      },
      {
        Sid    = "LogMetricFilters"
        Effect = "Allow"
        Action = [
          "logs:PutMetricFilter",
          "logs:DeleteMetricFilter",
          "logs:DescribeMetricFilters"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/aws/lambda/*hedgeye*"
      }
    ]
  })

  tags = var.tags
}

# Policy for read-only STS operations (for verification)
resource "aws_iam_policy" "sts_read" {
  name        = "${var.environment}-github-actions-sts-read"
  description = "Allow GitHub Actions to verify identity"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "STSGetCallerIdentity"
        Effect   = "Allow"
        Action   = "sts:GetCallerIdentity"
        Resource = "*"
      }
    ]
  })

  tags = var.tags
}

# Attach policies to role
resource "aws_iam_role_policy_attachment" "terraform_state" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.terraform_state.arn
}

resource "aws_iam_role_policy_attachment" "infrastructure" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.infrastructure.arn
}

resource "aws_iam_role_policy_attachment" "lambda_deployment" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.lambda_deployment.arn
}

resource "aws_iam_role_policy_attachment" "monitoring" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.monitoring.arn
}

resource "aws_iam_role_policy_attachment" "sts_read" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.sts_read.arn
}
