# Hedgeye Risk Tracker Infrastructure

This directory contains Terraform configuration for managing the Hedgeye Risk Ranges Tracker infrastructure on AWS.

## 🚀 Quick Start - Easy Environment Switching

**NEW: Safe, simple environment switching!**

Instead of complex commands, use these simple scripts:

```bash
./use-dev.sh         # Switch to dev (green)
./use-staging.sh     # Switch to staging (yellow)
./use-prod.sh        # Switch to production (red, requires confirmation)

./current-env.sh     # Check current environment
```

**See [ENVIRONMENT-SWITCHING.md](ENVIRONMENT-SWITCHING.md) for the complete guide.**

This replaces the error-prone manual `terraform init -reconfigure -backend-config=...` commands with safe, color-coded scripts that always show which environment you're working with.

---

## What This Infrastructure Manages

This Terraform configuration manages:
- **DynamoDB Tables**: Application data tables for ETF monitoring
  - `hedgeye-daily-risk-ranges` - Buy/sell trade levels
  - `hedgeye-weekly-risk-ranges` - Trend range data
- **Secrets Manager**: Secure storage for sensitive credentials
  - Gmail service account JSON credentials
  - Environment-specific secrets with 30-day recovery window
- **IAM Roles & Policies**: Execution role with least-privilege access
  - DynamoDB read/write permissions (scoped to specific tables)
  - Secrets Manager read-only access (for Gmail credentials)
  - CloudWatch Logs permissions (for application logging)
- **Backend State**: S3 bucket and DynamoDB table for Terraform state management

## Directory Structure

```
infrastructure/
├── main.tf                      # DynamoDB tables and IAM module
├── variables.tf                 # Variable definitions
├── outputs.tf                   # Output values
├── backend.tf                   # S3 backend configuration
├── terraform.tfvars.example     # Example variable values
├── modules/                     # Reusable Terraform modules
│   ├── iam/                     # IAM execution role module
│   │   ├── main.tf              # IAM role and policies
│   │   ├── variables.tf         # Module variables
│   │   └── outputs.tf           # Module outputs
│   └── secrets/                 # Secrets Manager module
│       ├── main.tf              # Secret definitions
│       ├── variables.tf         # Module variables
│       ├── outputs.tf           # Module outputs
│       └── README.md            # Secret management guide
├── bootstrap/                   # Backend resource setup (run once)
│   ├── backend-resources.tf     # S3 bucket and DynamoDB table
│   ├── README.md                # Bootstrap instructions
│   └── setup.sh                 # Automated setup script
├── environments/                # Environment-specific configs
│   ├── dev/
│   │   ├── backend-config.hcl   # Dev backend config
│   │   └── terraform.tfvars     # Dev variable values
│   ├── staging/
│   │   ├── backend-config.hcl   # Staging backend config
│   │   └── terraform.tfvars     # Staging variable values
│   └── prod/
│       ├── backend-config.hcl   # Prod backend config
│       └── terraform.tfvars     # Prod variable values
└── README.md                    # This file
```

## Getting Started

### First Time Setup

If this is your first time setting up the infrastructure, you need to create the S3 backend resources:

1. **Navigate to bootstrap directory:**
   ```bash
   cd infrastructure/bootstrap
   ```

2. **Run the bootstrap setup:**
   ```bash
   ./setup.sh
   ```

   This creates:
   - S3 bucket: `hedgeye-risk-tracker-terraform-state`
   - DynamoDB table: `terraform-state-lock`

3. **Return to infrastructure directory:**
   ```bash
   cd ..
   ```

4. **Initialize Terraform with remote backend** (for dev environment):
   ```bash
   terraform init -backend-config=environments/dev/backend-config.hcl
   ```

5. **Verify backend configuration:**
   ```bash
   terraform state list
   ```

See [bootstrap/README.md](bootstrap/README.md) for detailed setup instructions.

### Working with Existing Infrastructure

If the backend resources already exist:

```bash
# Navigate to infrastructure directory
cd infrastructure

# Switch to desired environment (recommended way)
./use-dev.sh

# View current state
terraform state list

# Plan changes
terraform plan -var-file="environments/dev/terraform.tfvars"

# Apply changes
terraform apply -var-file="environments/dev/terraform.tfvars"
```

## Managing DynamoDB Tables

### Creating Tables

The first time you set up an environment, you'll need to create the DynamoDB tables:

```bash
cd infrastructure

# Switch to dev environment
./use-dev.sh

# Review what will be created
terraform plan -var-file="environments/dev/terraform.tfvars"

# Create the tables
terraform apply -var-file="environments/dev/terraform.tfvars"
```

This creates two tables:
- `dev-hedgeye-daily-risk-ranges` - Stores buy/sell trade levels
- `dev-hedgeye-weekly-risk-ranges` - Stores trend range data

### Viewing Table Information

```bash
# Show all managed resources
terraform state list

# Show table details
terraform output

# Show specific table name
terraform output trade_ranges_table_name
```

### Updating Tables

When you need to modify table configuration:

```bash
# Make changes to main.tf or variables.tf

# Preview changes
terraform plan -var-file="environments/dev/terraform.tfvars"

# Apply changes (Terraform will show what's changing)
terraform apply -var-file="environments/dev/terraform.tfvars"
```

### Destroying Tables (Development Only)

**⚠️ WARNING: This deletes all data!**

```bash
# Only for development environment
./use-dev.sh

# Preview what will be destroyed
terraform plan -destroy -var-file="environments/dev/terraform.tfvars"

# Destroy tables (requires confirmation)
terraform destroy -var-file="environments/dev/terraform.tfvars"
```

**Production tables have deletion protection enabled and cannot be destroyed without removing that protection first.**

### Table Configuration

Each environment has different settings:

**Development (`dev`):**
- Deletion protection: ❌ Disabled (can recreate easily)
- Point-in-time recovery: ✅ Enabled
- Table prefix: `dev-`

**Staging (`staging`):**
- Deletion protection: ✅ Enabled
- Point-in-time recovery: ✅ Enabled
- Table prefix: `staging-`

**Production (`prod`):**
- Deletion protection: ✅ Enabled (required)
- Point-in-time recovery: ✅ Enabled (required)
- Table prefix: `prod-`

## IAM Roles and Policies

The infrastructure creates an IAM execution role with least-privilege policies for the application.

### Execution Role

**Name:** `{environment}-hedgeye-risk-tracker-execution-role`

The role is configured for Lambda execution with policies granting:

**DynamoDB Access:**
- Read/write operations on environment-specific tables only
- Actions: `PutItem`, `GetItem`, `UpdateItem`, `Query`, `Scan`, `BatchWriteItem`, `BatchGetItem`
- Resources: Scoped to `{env}-hedgeye-daily-risk-ranges` and `{env}-hedgeye-weekly-risk-ranges` tables

**Secrets Manager Access:**
- Read-only access to Gmail service account credentials
- Actions: `GetSecretValue`, `DescribeSecret`
- Resource: Scoped to `hedgeye-risk-tracker/gmail-service-account` secret

**CloudWatch Logs Access:**
- Create log groups, streams, and write log events
- Actions: `CreateLogGroup`, `CreateLogStream`, `PutLogEvents`
- Resource: Scoped to `/aws/lambda/{environment}-hedgeye-risk-tracker` log group

### Security Best Practices

✅ **Least Privilege** - Permissions scoped to specific resources only
✅ **No Wildcards** - All policies specify exact resource ARNs
✅ **Read-Only Secrets** - No write/delete permissions for Secrets Manager
✅ **Environment Isolation** - Each environment has its own role with separate resource access

### Viewing IAM Role Information

```bash
# Show IAM role ARN
terraform output execution_role_arn

# Show IAM role name
terraform output execution_role_name
```

## Secrets Manager

The infrastructure creates AWS Secrets Manager secrets for securely storing sensitive credentials.

### Gmail Service Account Secret

**Name:** `{environment}/hedgeye/gmail-service-account`

This secret stores the Gmail API service account JSON credentials for domain-wide delegation.

### Creating and Populating Secrets

**Important:** Secret values are NOT managed by Terraform (security best practice). After Terraform creates the secret, you must manually set the value:

```bash
# Using AWS CLI
aws secretsmanager put-secret-value \
  --secret-id dev/hedgeye/gmail-service-account \
  --secret-string file://service-account.json

# Verify secret was set
aws secretsmanager get-secret-value \
  --secret-id dev/hedgeye/gmail-service-account \
  --query SecretString \
  --output text
```

Or use AWS Console:
1. Navigate to AWS Secrets Manager
2. Find secret: `{environment}/hedgeye/gmail-service-account`
3. Click "Retrieve secret value" → "Edit"
4. Paste service account JSON → "Save"

### Viewing Secret Information

```bash
# Show secret ARN
terraform output gmail_secret_arn

# Show secret name
terraform output gmail_secret_name

# Retrieve secret value (requires IAM permissions)
aws secretsmanager get-secret-value \
  --secret-id $(terraform output -raw gmail_secret_name)
```

### Secret Configuration

**Security Features:**
- ✅ KMS encryption with AWS managed key
- ✅ 30-day recovery window for accidental deletion
- ✅ Environment-specific secrets for isolation
- ✅ Access restricted to application execution role
- ✅ All access logged in CloudTrail

**Rotation:** Service account keys typically don't require automatic rotation. For manual rotation, generate a new key in Google Cloud Console and update the secret value.

See [modules/secrets/README.md](modules/secrets/README.md) for complete secret management documentation.

## Environment Management

The infrastructure supports multiple environments (dev, staging, prod) using the same S3 bucket with different state file paths:

- **Dev:** `hedgeye-risk-tracker/dev/terraform.tfstate`
- **Staging:** `hedgeye-risk-tracker/staging/terraform.tfstate`
- **Prod:** `hedgeye-risk-tracker/prod/terraform.tfstate`

### Switching Environments

To switch between environments, re-initialize with the appropriate backend config:

```bash
# Switch to staging
terraform init -reconfigure -backend-config=environments/staging/backend-config.hcl

# Switch to production
terraform init -reconfigure -backend-config=environments/prod/backend-config.hcl

# Switch back to dev
terraform init -reconfigure -backend-config=environments/dev/backend-config.hcl
```

**Note:** The `-reconfigure` flag is needed when switching between different backend configurations.

## Remote State Benefits

Using S3 backend with DynamoDB locking provides:

✅ **Team Collaboration** - Multiple team members can work with the same state
✅ **State Locking** - Prevents concurrent modifications that could corrupt state
✅ **State Versioning** - S3 versioning allows rollback to previous states
✅ **Encryption** - State is encrypted at rest (AES-256)
✅ **Backup** - State is stored durably in S3
✅ **History** - All state changes are versioned

## Backend Configuration

The `backend.tf` file configures the S3 backend. Actual values are loaded from environment-specific `.hcl` files.

### backend.tf
```hcl
terraform {
  backend "s3" {
    # Values loaded from backend-config.hcl
  }
}
```

### Backend Config Files

Each environment has its own configuration in `environments/{env}/backend-config.hcl`:

```hcl
bucket         = "hedgeye-risk-tracker-terraform-state"
key            = "hedgeye-risk-tracker/dev/terraform.tfstate"
region         = "us-west-2"
encrypt        = true
dynamodb_table = "terraform-state-lock"
```

## State Locking

DynamoDB table `terraform-state-lock` prevents concurrent Terraform operations:

- When you run `terraform apply`, Terraform acquires a lock
- Other operations wait until the lock is released
- If Terraform crashes, the lock may need manual cleanup:

```bash
# Force unlock (use carefully!)
terraform force-unlock <lock-id>
```

## State Management Commands

### Viewing State

```bash
# List all resources in state
terraform state list

# Show details of a specific resource
terraform state show aws_dynamodb_table.example

# Pull current state to local file
terraform state pull > current-state.json
```

### Migrating State

If you need to migrate from local state to remote backend:

```bash
terraform init -migrate-state -backend-config=environments/dev/backend-config.hcl
```

Terraform will prompt you to confirm the migration.

## Security Best Practices

### State File Security

⚠️ **Warning:** Terraform state files may contain sensitive information:
- Resource IDs and ARNs
- Configuration values
- Some resource attributes
- Potentially secrets (though this should be avoided)

### Security Measures in Place

1. **Encryption at Rest:** S3 server-side encryption (AES-256)
2. **Encryption in Transit:** All access uses HTTPS
3. **Access Control:** S3 bucket blocks all public access
4. **Versioning:** Enabled for recovery
5. **IAM Policies:** Restrict access to authorized users only

### Recommendations

- Never commit state files to version control
- Use `sensitive = true` for sensitive outputs
- Store secrets in AWS Secrets Manager, not Terraform variables
- Regularly rotate AWS credentials
- Enable CloudTrail logging for state bucket access (production)
- Consider MFA delete for production state bucket

## IAM Permissions

Users/roles working with Terraform need these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::hedgeye-risk-tracker-terraform-state",
        "arn:aws:s3:::hedgeye-risk-tracker-terraform-state/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:us-west-2:*:table/terraform-state-lock"
    }
  ]
}
```

Plus permissions for the specific AWS resources you're managing (DynamoDB, Lambda, etc.).

## Troubleshooting

### Backend Initialization Failed

**Error:** `Error loading state: AccessDenied`

**Solution:** Verify your AWS credentials have permissions to access the S3 bucket and DynamoDB table.

```bash
# Test S3 access
aws s3 ls s3://hedgeye-risk-tracker-terraform-state/

# Test DynamoDB access
aws dynamodb describe-table --table-name terraform-state-lock
```

### State Lock Already Exists

**Error:** `Error locking state: ConditionalCheckFailedException`

**Cause:** A previous Terraform operation didn't release the lock (due to crash or interruption).

**Solution:**

1. Verify no other Terraform operations are running
2. Force unlock with the lock ID from the error message:
   ```bash
   terraform force-unlock <lock-id>
   ```

### Wrong Environment State

**Error:** State doesn't match expected resources

**Cause:** Initialized with wrong backend config (wrong environment)

**Solution:** Re-initialize with correct environment config:

```bash
terraform init -reconfigure -backend-config=environments/dev/backend-config.hcl
```

## State Recovery

If state becomes corrupted or you need to rollback:

### View Available Versions

```bash
aws s3api list-object-versions \
    --bucket hedgeye-risk-tracker-terraform-state \
    --prefix hedgeye-risk-tracker/dev/terraform.tfstate
```

### Restore Previous Version

```bash
# Download specific version
aws s3api get-object \
    --bucket hedgeye-risk-tracker-terraform-state \
    --key hedgeye-risk-tracker/dev/terraform.tfstate \
    --version-id <version-id> \
    old-state.tfstate

# Push it back (manually, with caution)
terraform state push old-state.tfstate
```

**Warning:** State recovery should be done carefully. Consider consulting with the team first.

## Cost Monitoring

The backend resources cost less than $1/month:

- **S3 Storage:** ~$0.023/GB/month (state files are typically < 1MB)
- **S3 Requests:** < $0.01/month for typical usage
- **DynamoDB:** ~$0.01-0.10/month with PAY_PER_REQUEST billing

Monitor costs in AWS Cost Explorer or enable budget alerts.

## Migration from recreate_tables.py

This Terraform configuration replaces the `recreate_tables.py` script with a safer, more maintainable approach.

### Benefits of Terraform vs Script

**Old approach (`recreate_tables.py`):**
- ❌ Deletes all data every time it runs
- ❌ No preview of changes
- ❌ No environment separation
- ❌ No version control of schema changes
- ❌ Manual execution required

**New approach (Terraform):**
- ✅ Idempotent - safe to run multiple times
- ✅ Preview changes with `terraform plan`
- ✅ Environment separation (dev/staging/prod)
- ✅ Schema changes tracked in git
- ✅ Can integrate into CI/CD
- ✅ Deletion protection for production
- ✅ Point-in-time recovery enabled

### Migration Path

If you have existing tables created by `recreate_tables.py`:

**Option 1: Import Existing Tables (Recommended)**

```bash
cd infrastructure
./use-dev.sh

# Import existing tables into Terraform state
terraform import -var-file="environments/dev/terraform.tfvars" \
  aws_dynamodb_table.trade_ranges etf_monitoring_trade_ranges

terraform import -var-file="environments/dev/terraform.tfvars" \
  aws_dynamodb_table.trend_ranges etf_monitoring_trend_ranges

# Verify state
terraform state list
terraform plan -var-file="environments/dev/terraform.tfvars"
```

**Option 2: Recreate Tables (Development Only)**

```bash
# Delete old tables using recreate script or AWS console
# Then create new tables with Terraform
cd infrastructure
./use-dev.sh
terraform apply -var-file="environments/dev/terraform.tfvars"
```

### Table Name Changes

The new Terraform tables use environment prefixes:

| Old Name (Script)              | New Name (Terraform Dev)           |
|--------------------------------|------------------------------------|
| `etf_monitoring_trade_ranges`  | `dev-hedgeye-daily-risk-ranges` |
| `etf_monitoring_trend_ranges`  | `dev-hedgeye-weekly-risk-ranges` |

**Important:** You'll need to update your application code to use the new table names, or configure the table names via environment variables.

### Deprecating recreate_tables.py

The `recreate_tables.py` script is kept in the repository for reference but should not be used for new environments. Use Terraform instead for all table management.

## Additional Resources

- [Terraform S3 Backend Documentation](https://www.terraform.io/docs/language/settings/backends/s3.html)
- [Terraform State Documentation](https://www.terraform.io/docs/language/state/index.html)
- [AWS S3 Security Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)
- [Bootstrap Setup Guide](bootstrap/README.md)

## Support

For questions or issues:
1. Check the troubleshooting section above
2. Review the bootstrap README for setup issues
3. Consult Terraform and AWS documentation
4. Open an issue in the project repository
