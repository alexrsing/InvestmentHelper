# Lambda Module - Outputs
#
# Exports Lambda function details for use by other modules

output "function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.this.arn
}

output "function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.this.function_name
}

output "invoke_arn" {
  description = "ARN used to invoke the Lambda function"
  value       = aws_lambda_function.this.invoke_arn
}

output "function_url" {
  description = "URL of the Lambda function (if enabled)"
  value       = var.enable_function_url ? aws_lambda_function_url.this[0].function_url : null
}

output "log_group_name" {
  description = "Name of the CloudWatch Log Group"
  value       = aws_cloudwatch_log_group.lambda.name
}

output "log_group_arn" {
  description = "ARN of the CloudWatch Log Group"
  value       = aws_cloudwatch_log_group.lambda.arn
}

output "version" {
  description = "Published version of the Lambda function"
  value       = aws_lambda_function.this.version
}

output "last_modified" {
  description = "Last modified timestamp of the Lambda function"
  value       = aws_lambda_function.this.last_modified
}
