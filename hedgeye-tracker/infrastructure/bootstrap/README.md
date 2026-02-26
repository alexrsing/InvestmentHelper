# Terraform Backend Bootstrap

This directory contains Terraform configuration and scripts to create the S3 bucket and DynamoDB table required for remote state storage.

## Overview

Terraform needs an S3 bucket and DynamoDB table to store state remotely and enable state locking. However, these resources must exist before Terraform can use them as a backend. This creates a "chicken and egg" problem.

**Solution:** Use this separate Terraform configuration to create the backend resources first, then configure the main infrastructure to use them.

## Prerequisites

- AWS CLI installed and configured
- Terraform >= 1.0 installed
- AWS credentials with permissions to create:
  - S3 buckets
  - DynamoDB tables
  - IAM policies (for bucket policies)

## Quick Start

### Automated Setup (Recommended)

```bash
cd infrastructure/bootstrap
./setup.sh
```

This will:
1. Initialize Terraform
2. Create an execution plan
3. Prompt for confirmation
4. Create the S3 bucket and DynamoDB table
5. Display the resource names

### Manual Setup

If you prefer manual control:

```bash
cd infrastructure/bootstrap

# Initialize Terraform
terraform init

# Plan the infrastructure
terraform plan -var="org_name=hedgeye-risk-tracker" -var="aws_region=us-west-2"

# Apply the changes
terraform apply -var="org_name=hedgeye-risk-tracker" -var="aws_region=us-west-2"

# View outputs
terraform output
```

## Configuration Variables

You can customize the resources by setting variables:

- `org_name` - Organization name for S3 bucket (default: `hedgeye-risk-tracker`)
- `aws_region` - AWS region (default: `us-west-2`)

### Custom Organization Name

```bash
./setup.sh my-company us-east-1
```

Or with Terraform directly:

```bash
terraform apply \
    -var="org_name=my-company" \
    -var="aws_region=us-east-1"
```

## Resources Created

### S3 Bucket

- **Name:** `{org_name}-terraform-state`
- **Versioning:** Enabled (for state recovery)
- **Encryption:** AES-256 server-side encryption
- **Public Access:** Blocked (all settings)
- **Lifecycle Policy:**
  - Old versions expire after 90 days
  - Incomplete multipart uploads aborted after 7 days

### DynamoDB Table

- **Name:** `terraform-state-lock`
- **Partition Key:** `LockID` (String)
- **Billing Mode:** PAY_PER_REQUEST (low cost for infrequent access)
- **Point-in-time Recovery:** Enabled

## Next Steps

After running the bootstrap:

1. **Note the bucket name** from the output (usually `hedgeye-risk-tracker-terraform-state`)

2. **Verify the backend config files** in `infrastructure/environments/*/backend-config.hcl` have the correct bucket name

3. **Navigate to main infrastructure:**
   ```bash
   cd ../
   ```

4. **Initialize the backend** (for dev environment):
   ```bash
   terraform init -backend-config=environments/dev/backend-config.hcl
   ```

5. **Migrate existing state** (if you have local state):
   ```bash
   terraform init -migrate-state -backend-config=environments/dev/backend-config.hcl
   ```

## Verifying the Setup

Check that resources were created:

```bash
# List S3 bucket
aws s3 ls | grep terraform-state

# Describe DynamoDB table
aws dynamodb describe-table --table-name terraform-state-lock

# View Terraform outputs
terraform output
```

## Cost Estimate

Expected monthly costs for the backend resources:

- **S3 Storage:** ~$0.023/GB/month (state files are typically < 1MB)
- **S3 Requests:** Minimal (< $0.01/month for typical usage)
- **DynamoDB:** ~$0.01-0.10/month with PAY_PER_REQUEST

**Total:** Less than $1/month for typical usage

## Security Considerations

The bootstrap creates secure resources:

- ✅ S3 bucket versioning enabled (recovery)
- ✅ S3 encryption at rest (AES-256)
- ✅ S3 public access blocked
- ✅ DynamoDB point-in-time recovery
- ✅ Lifecycle policies for cleanup

### State File Security

**Warning:** Terraform state files may contain sensitive data (resource IDs, configuration values, etc.)

**Mitigations in place:**
- Encryption at rest (S3 server-side encryption)
- Encryption in transit (HTTPS only)
- No public access (bucket policy)
- Versioning for recovery
- CloudTrail can audit access (optional)

## IAM Permissions Required

The AWS credentials used need these permissions:

### For Bootstrap

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:PutBucketVersioning",
        "s3:PutEncryptionConfiguration",
        "s3:PutBucketPublicAccessBlock",
        "s3:PutLifecycleConfiguration",
        "s3:GetBucket*",
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::*-terraform-state"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DescribeTable",
        "dynamodb:UpdateContinuousBackups",
        "dynamodb:TagResource"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/terraform-state-lock"
    }
  ]
}
```

### For Terraform Backend Usage

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
      "Resource": "arn:aws:dynamodb:*:*:table/terraform-state-lock"
    }
  ]
}
```

## Troubleshooting

### Bucket Name Already Exists

S3 bucket names must be globally unique. If you get an error about the bucket name existing:

```bash
terraform apply -var="org_name=your-unique-name"
```

### AWS Credentials Not Found

Ensure your AWS credentials are configured:

```bash
aws configure
# Or use environment variables:
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-west-2
```

### Permission Denied

Your AWS credentials need permissions to create S3 buckets and DynamoDB tables. Contact your AWS administrator.

## State Management for Bootstrap

The bootstrap itself uses **local state** (stored in this directory as `terraform.tfstate`). This is acceptable because:

1. Bootstrap runs once (or very rarely)
2. Resources are simple and can be recreated
3. No team collaboration needed for bootstrap

**Important:** Keep `terraform.tfstate` in this directory safe, or commit it to version control (if your repo is private).

## Destroying Bootstrap Resources

**Warning:** Destroying these resources will break Terraform state management for all environments.

Only destroy if you're completely tearing down the infrastructure:

```bash
# First, ensure all environments have migrated their state elsewhere
# Then destroy the bootstrap resources
terraform destroy -var="org_name=hedgeye-risk-tracker"
```

## Multiple Environments

The S3 bucket and DynamoDB table are **shared across all environments** (dev, staging, prod). Each environment uses:

- Same S3 bucket
- Different key paths (e.g., `hedgeye-risk-tracker/dev/terraform.tfstate`)
- Same DynamoDB lock table

This is cost-effective and simplifies management.

## Additional Resources

- [Terraform S3 Backend Documentation](https://www.terraform.io/docs/backends/types/s3.html)
- [AWS S3 Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)
- [Terraform State Best Practices](https://www.terraform.io/docs/state/index.html)
