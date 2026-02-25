# Bootstrap configuration for Production (us-east-1)
# Usage: terraform apply -var-file=prod.tfvars -state=terraform-prod.tfstate

aws_region        = "us-east-1"
state_bucket_name = "price-fetcher-terraform-state-prod"
lock_table_name   = "price-fetcher-terraform-lock-prod"
