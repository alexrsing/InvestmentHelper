# IAM Module - Outputs
#
# Exports role ARN and name for use by compute resources

output "execution_role_arn" {
  description = "ARN of the IAM execution role for Lambda function"
  value       = aws_iam_role.execution_role.arn
}

output "execution_role_name" {
  description = "Name of the IAM execution role"
  value       = aws_iam_role.execution_role.name
}

output "execution_role_id" {
  description = "Unique ID of the IAM execution role"
  value       = aws_iam_role.execution_role.id
}
