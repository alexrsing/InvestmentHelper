# Backend configuration for Dev environment
# Usage: terraform init -backend-config=environments/dev/backend-config.hcl

bucket         = "hedgeye-risk-tracker-terraform-state"
key            = "hedgeye-risk-tracker/dev/terraform.tfstate"
region         = "us-east-1"
encrypt        = true
dynamodb_table = "terraform-state-lock"
