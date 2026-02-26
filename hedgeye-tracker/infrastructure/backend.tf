# Terraform S3 Backend Configuration
#
# This file configures remote state storage in S3 with DynamoDB locking.
# The actual backend values are loaded from environment-specific .hcl files.
#
# Prerequisites:
# 1. Run bootstrap to create S3 bucket and DynamoDB table
# 2. Initialize with environment config:
#    terraform init -backend-config=environments/dev/backend-config.hcl
#
# Migration from local state:
#    terraform init -migrate-state -backend-config=environments/dev/backend-config.hcl

terraform {
  backend "s3" {
    # Configuration values loaded from backend-config.hcl files
    # Do not hardcode values here to support multiple environments
  }
}
