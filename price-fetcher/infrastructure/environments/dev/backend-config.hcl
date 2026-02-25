# Backend configuration for Dev environment
# Usage: terraform init -backend-config=environments/dev/backend-config.hcl

bucket         = "price-fetcher-terraform-state"
key            = "price-fetcher/dev/terraform.tfstate"
region         = "us-west-2"
encrypt        = true
dynamodb_table = "price-fetcher-terraform-lock"
