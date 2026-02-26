# Secrets Manager Module - Outputs
#
# Exports secret ARN and name for use by IAM policies and application

output "gmail_secret_arn" {
  description = "ARN of the Gmail service account secret"
  value       = aws_secretsmanager_secret.gmail_service_account.arn
}

output "gmail_secret_name" {
  description = "Name of the Gmail service account secret"
  value       = aws_secretsmanager_secret.gmail_service_account.name
}

output "gmail_secret_id" {
  description = "Unique identifier of the Gmail service account secret"
  value       = aws_secretsmanager_secret.gmail_service_account.id
}
