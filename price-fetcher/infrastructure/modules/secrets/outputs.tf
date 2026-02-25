# Secrets Module Outputs

output "config_secret_arn" {
  description = "ARN of the price fetcher config secret"
  value       = aws_secretsmanager_secret.config.arn
}

output "config_secret_name" {
  description = "Name of the price fetcher config secret"
  value       = aws_secretsmanager_secret.config.name
}

output "all_secret_arns" {
  description = "List of all secret ARNs (for IAM policy)"
  value       = [aws_secretsmanager_secret.config.arn]
}
