# Backend configuration for Staging environment
# Usage: terraform init -backend-config=environments/staging/backend-config.hcl

bucket         = "price-fetcher-terraform-state"
key            = "price-fetcher/staging/terraform.tfstate"
region         = "us-west-2"
encrypt        = true
dynamodb_table = "price-fetcher-terraform-lock"
