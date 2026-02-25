# Price Fetcher Infrastructure

Infrastructure as Code for deploying the price-fetcher application to AWS Lambda using Terraform.

## Architecture

```
                                    ┌─────────────────┐
                                    │  EventBridge    │
                                    │   Scheduler     │
                                    └────────┬────────┘
                                             │ triggers
    ┌────────────────────────────────────────┼────────────────────────────────────────┐
    │                                        ▼                                        │
    │  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐            │
    │  │  Price Fetcher   │   │ Holiday Fetcher  │   │    Validator     │   Lambda   │
    │  │     Lambda       │   │     Lambda       │   │     Lambda       │            │
    │  └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘            │
    └───────────┼──────────────────────┼──────────────────────┼───────────────────────┘
                │                      │                      │
                ▼                      ▼                      ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                         DynamoDB                                 │
    │                      (price data)                               │
    └─────────────────────────────────────────────────────────────────┘
                │
                ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    Secrets Manager                              │
    │           (API keys: Alpha Vantage, Twelve Data, etc.)         │
    └─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- **Terraform** >= 1.0
- **AWS CLI** configured with appropriate credentials
- **GitHub repository** access (for OIDC CI/CD)

## Quick Start

### 1. Bootstrap (First-Time Setup)

Create the S3 bucket and DynamoDB table for Terraform state:

```bash
cd infrastructure/bootstrap
terraform init
terraform apply
```

See [bootstrap/README.md](bootstrap/README.md) for details.

### 2. Initialize Infrastructure

```bash
cd infrastructure
./use-dev.sh  # Initialize for dev environment
```

### 3. Deploy

```bash
terraform plan -var-file=environments/dev/terraform.tfvars
terraform apply -var-file=environments/dev/terraform.tfvars
```

### 4. Configure API Keys

After deployment, configure your API keys in Secrets Manager:

```bash
aws secretsmanager put-secret-value \
  --secret-id dev/price-fetcher/alpha-vantage-api-key \
  --secret-string "YOUR_API_KEY"
```

See outputs for secret names: `terraform output secret_names`

## Directory Structure

```
infrastructure/
├── main.tf                      # Main orchestration (module composition)
├── variables.tf                 # Root input variables
├── outputs.tf                   # Root outputs
├── backend.tf                   # S3 backend configuration
│
├── environments/                # Environment-specific configs
│   ├── dev/
│   │   ├── terraform.tfvars     # Dev variable values
│   │   └── backend-config.hcl   # Dev state location
│   ├── staging/
│   └── prod/
│
├── modules/                     # Reusable Terraform modules
│   ├── iam/                     # Lambda execution role
│   ├── secrets/                 # Secrets Manager secrets
│   ├── lambda/                  # Lambda functions
│   ├── scheduler/               # EventBridge rules
│   ├── monitoring/              # CloudWatch alarms
│   └── github-oidc/             # GitHub Actions auth
│
├── bootstrap/                   # One-time state backend setup
│
├── use-dev.sh                   # Switch to dev environment
├── use-staging.sh               # Switch to staging
├── use-prod.sh                  # Switch to prod (with confirmation)
└── current-env.sh               # Show current environment
```

## Modules

| Module | Purpose | Key Resources |
|--------|---------|---------------|
| **iam** | Lambda execution permissions | IAM Role, Policies |
| **secrets** | API key storage | Secrets Manager secrets |
| **lambda** | Function deployment | Lambda functions, Log Groups |
| **scheduler** | Scheduled execution | EventBridge rules |
| **monitoring** | Alerting | CloudWatch Alarms, SNS Topics |
| **github-oidc** | CI/CD authentication | OIDC Provider, IAM Role |

## Environment Configuration

### Feature Flags

Control which components are deployed:

```hcl
enable_lambda     = true   # Lambda functions
enable_scheduler  = true   # EventBridge schedules
enable_monitoring = true   # CloudWatch alarms
enable_github_oidc = true  # GitHub Actions auth
```

### Environment Differences

| Setting | Dev | Staging | Prod |
|---------|-----|---------|------|
| Memory | 512 MB | 512 MB | 1024 MB |
| Log Retention | 30 days | 60 days | 90 days |
| Deletion Protection | No | Yes | Yes |
| Fetch Frequency | 15 min | 15 min | 5 min |
| Scheduler | Enabled | Enabled | Disabled* |
| Monitoring | Enabled | Enabled | Disabled* |

*Production starts with scheduler/monitoring disabled for safe rollout.

## Deployment Workflow

### Daily Development

```bash
# 1. Check current environment
./current-env.sh

# 2. Switch if needed
./use-dev.sh

# 3. Make changes and plan
terraform plan -var-file=environments/dev/terraform.tfvars

# 4. Apply changes
terraform apply -var-file=environments/dev/terraform.tfvars
```

### Production Deployment

```bash
# 1. Switch to prod (requires confirmation)
./use-prod.sh

# 2. Always plan first
terraform plan -var-file=environments/prod/terraform.tfvars

# 3. Review carefully, then apply
terraform apply -var-file=environments/prod/terraform.tfvars
```

### Lambda Code Deployment

```bash
# Package the Lambda code
./deployment/package-lambda.sh

# Deploy to Lambda
aws lambda update-function-code \
  --function-name dev-price-fetcher \
  --zip-file fileb://deployment/build/lambda.zip
```

## Security

### IAM (Least Privilege)

- Lambda role only has access to:
  - Specific DynamoDB tables (environment-prefixed)
  - Specific Secrets Manager secrets (environment-prefixed)
  - CloudWatch Logs (specific log groups)

### Secrets Management

- API keys stored in AWS Secrets Manager
- Never committed to version control
- Lambda retrieves at runtime
- Separate secrets per environment

### CI/CD Authentication

- GitHub Actions uses OIDC (no static credentials)
- Trust policy scoped to specific repository
- Environment-specific deployment roles

### Environment Isolation

- Separate state files per environment
- Resource naming includes environment prefix
- No cross-environment access

## Outputs

After deployment, view key outputs:

```bash
# Lambda function names
terraform output lambda_functions

# Secret names for API key configuration
terraform output secret_names

# GitHub Actions role ARN (for CI/CD setup)
terraform output github_actions_role_arn
```

## Related Documentation

- [Bootstrap Setup](bootstrap/README.md) - First-time backend setup
- [Environment Switching](ENVIRONMENT-SWITCHING.md) - Safe environment management
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
