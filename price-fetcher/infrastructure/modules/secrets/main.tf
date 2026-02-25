# Secrets Module - Single JSON Secret
# Creates one Secrets Manager secret containing all API keys and configuration.
#
# IMPORTANT: This module creates the secret WITHOUT a value.
# Set the value manually after deployment:
#   aws secretsmanager put-secret-value \
#     --secret-id <env>/price-fetcher/config \
#     --secret-string '{"ALPHA_VANTAGE_API_KEY":"...","ALPHA_VANTAGE_TIER":"free",...}'

resource "aws_secretsmanager_secret" "config" {
  name                    = "${var.environment}/price-fetcher/config"
  description             = "Price fetcher API keys and configuration (JSON)"
  recovery_window_in_days = var.recovery_window_days

  tags = merge(var.tags, {
    Environment = var.environment
    Module      = "secrets"
  })
}
