# Outputs for GitHub OIDC Module

output "oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC provider"
  value       = aws_iam_openid_connect_provider.github_actions.arn
}

output "role_arn" {
  description = "ARN of the IAM role for GitHub Actions"
  value       = aws_iam_role.github_actions.arn
}

output "role_name" {
  description = "Name of the IAM role for GitHub Actions"
  value       = aws_iam_role.github_actions.name
}

output "policy_arns" {
  description = "ARNs of all attached policies"
  value = {
    terraform_state   = aws_iam_policy.terraform_state.arn
    infrastructure    = aws_iam_policy.infrastructure.arn
    lambda_deployment = aws_iam_policy.lambda_deployment.arn
    monitoring        = aws_iam_policy.monitoring.arn
    sts_read          = aws_iam_policy.sts_read.arn
  }
}
