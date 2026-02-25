# Backend configuration for Production environment
# Usage: terraform init -backend-config=environments/prod/backend-config.hcl

bucket         = "price-fetcher-terraform-state"
key            = "price-fetcher/prod/terraform.tfstate"
region         = "us-west-2"
encrypt        = true
dynamodb_table = "price-fetcher-terraform-lock"
