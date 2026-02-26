# Backend configuration for Staging environment
# Usage: terraform init -backend-config=environments/staging/backend-config.hcl

bucket         = "hedgeye-risk-tracker-terraform-state"
key            = "hedgeye-risk-tracker/staging/terraform.tfstate"
region         = "us-east-1"
encrypt        = true
dynamodb_table = "terraform-state-lock"
