# DynamoDB Module Outputs

output "watchlist_table_name" {
  description = "Name of the watchlist table"
  value       = aws_dynamodb_table.watchlist.name
}

output "watchlist_table_arn" {
  description = "ARN of the watchlist table"
  value       = aws_dynamodb_table.watchlist.arn
}

output "prices_table_name" {
  description = "Name of the prices table (if created)"
  value       = var.create_prices_table ? aws_dynamodb_table.prices[0].name : ""
}

output "prices_table_arn" {
  description = "ARN of the prices table (if created)"
  value       = var.create_prices_table ? aws_dynamodb_table.prices[0].arn : ""
}

output "config_table_name" {
  description = "Name of the config table (if created)"
  value       = var.create_config_table ? aws_dynamodb_table.config[0].name : ""
}

output "config_table_arn" {
  description = "ARN of the config table (if created)"
  value       = var.create_config_table ? aws_dynamodb_table.config[0].arn : ""
}

output "all_table_arns" {
  description = "List of all table ARNs managed by this module"
  value = compact([
    aws_dynamodb_table.watchlist.arn,
    var.create_prices_table ? aws_dynamodb_table.prices[0].arn : "",
    var.create_config_table ? aws_dynamodb_table.config[0].arn : "",
  ])
}
