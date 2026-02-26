# Backend configuration for Production environment
# Usage: terraform init -backend-config=environments/prod/backend-config.hcl

bucket         = "hedgeye-risk-tracker-terraform-state"
key            = "hedgeye-risk-tracker/prod/terraform.tfstate"
region         = "us-east-1"
encrypt        = true
dynamodb_table = "terraform-state-lock"
