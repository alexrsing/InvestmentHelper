# Lambda Module Outputs

# Price Fetcher (main)
output "price_fetcher_arn" {
  description = "ARN of the price fetcher Lambda function"
  value       = aws_lambda_function.price_fetcher.arn
}

output "price_fetcher_name" {
  description = "Name of the price fetcher Lambda function"
  value       = aws_lambda_function.price_fetcher.function_name
}

output "price_fetcher_invoke_arn" {
  description = "Invoke ARN for API Gateway integration"
  value       = aws_lambda_function.price_fetcher.invoke_arn
}

# Holiday Fetcher
output "holiday_fetcher_arn" {
  description = "ARN of the holiday fetcher Lambda function"
  value       = aws_lambda_function.holiday_fetcher.arn
}

output "holiday_fetcher_name" {
  description = "Name of the holiday fetcher Lambda function"
  value       = aws_lambda_function.holiday_fetcher.function_name
}

# Validator
output "validator_arn" {
  description = "ARN of the validator Lambda function"
  value       = aws_lambda_function.validator.arn
}

output "validator_name" {
  description = "Name of the validator Lambda function"
  value       = aws_lambda_function.validator.function_name
}

# Log Groups
output "price_fetcher_log_group_arn" {
  description = "ARN of the price fetcher CloudWatch log group"
  value       = aws_cloudwatch_log_group.price_fetcher.arn
}

output "price_fetcher_log_group_name" {
  description = "Name of the price fetcher CloudWatch log group"
  value       = aws_cloudwatch_log_group.price_fetcher.name
}

output "all_log_group_arns" {
  description = "List of all Lambda log group ARNs (for IAM policy)"
  value = [
    aws_cloudwatch_log_group.price_fetcher.arn,
    aws_cloudwatch_log_group.holiday_fetcher.arn,
    aws_cloudwatch_log_group.validator.arn,
  ]
}

# All function names (for scheduler module)
output "all_function_names" {
  description = "Map of all Lambda function names"
  value = {
    price_fetcher   = aws_lambda_function.price_fetcher.function_name
    holiday_fetcher = aws_lambda_function.holiday_fetcher.function_name
    validator       = aws_lambda_function.validator.function_name
  }
}

# All function ARNs (for scheduler module)
output "all_function_arns" {
  description = "Map of all Lambda function ARNs"
  value = {
    price_fetcher   = aws_lambda_function.price_fetcher.arn
    holiday_fetcher = aws_lambda_function.holiday_fetcher.arn
    validator       = aws_lambda_function.validator.arn
  }
}
