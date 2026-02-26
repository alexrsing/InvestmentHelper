# Secrets Manager Module - Main Configuration
#
# This module creates AWS Secrets Manager secrets for securely storing
# Gmail service account credentials

# Gmail Service Account Secret
# Stores the service account JSON credentials for Gmail API access
resource "aws_secretsmanager_secret" "gmail_service_account" {
  name        = "${var.environment}/hedgeye/gmail-service-account"
  description = "Gmail service account credentials for Hedgeye Risk Tracker ${var.environment} environment"

  # Recovery window for accidental deletion (30 days recommended)
  recovery_window_in_days = var.recovery_window_days

  # Note: Automatic rotation is not configured for service account keys
  # Service account keys are typically rotated manually when needed

  tags = merge(
    var.tags,
    {
      Name        = "${var.environment}/hedgeye/gmail-service-account"
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "hedgeye-risk-tracker"
      Purpose     = "gmail-api-credentials"
    }
  )
}

# Note: Secret value is NOT managed by Terraform for security reasons.
# After creating the secret, set the value manually using:
#
#   aws secretsmanager put-secret-value \
#     --secret-id ${var.environment}/hedgeye/gmail-service-account \
#     --secret-string file://service-account.json
#
# Or use AWS Console to add the secret value.
