# Terraform Bootstrap

One-time setup for Terraform remote state management.

## Overview

This bootstrap creates:
- **S3 Bucket** (`price-fetcher-terraform-state`) - Stores Terraform state files
- **DynamoDB Table** (`price-fetcher-terraform-lock`) - Prevents concurrent state modifications

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.6.0
- [AWS CLI](https://aws.amazon.com/cli/) configured with credentials
- IAM permissions for S3 and DynamoDB

## Setup

### 1. Run Bootstrap Script

```bash
cd infrastructure/bootstrap
./setup.sh
```

The script will:
1. Verify prerequisites
2. Show planned resources
3. Create S3 bucket and DynamoDB table
4. Output backend configuration

### 2. Configure Main Infrastructure Backend

After bootstrap completes, create `infrastructure/backend.tf`:

```hcl
terraform {
  backend "s3" {
    bucket         = "price-fetcher-terraform-state"
    key            = "price-fetcher/dev/terraform.tfstate"  # Change per environment
    region         = "us-west-2"
    dynamodb_table = "price-fetcher-terraform-lock"
    encrypt        = true
  }
}
```

### 3. Initialize Main Infrastructure

```bash
cd infrastructure
terraform init
```

## State File Paths

Each environment uses a separate state file:

| Environment | State Key |
|-------------|-----------|
| dev | `price-fetcher/dev/terraform.tfstate` |
| staging | `price-fetcher/staging/terraform.tfstate` |
| prod | `price-fetcher/prod/terraform.tfstate` |

## Security Features

- **Versioning**: S3 bucket versioning enabled for state recovery
- **Encryption**: Server-side encryption with AES-256
- **Public Access Blocked**: All public access denied
- **Deletion Protection**: `prevent_destroy` lifecycle rule

## Manual Setup (Alternative)

If you prefer not to use the script:

```bash
cd infrastructure/bootstrap
terraform init
terraform plan
terraform apply
```

## Troubleshooting

### "Bucket already exists"
The S3 bucket name is globally unique. If it exists in another account, modify `state_bucket_name` in `variables.tf`.

### "Access Denied"
Ensure your AWS credentials have permissions:
- `s3:CreateBucket`, `s3:PutBucketVersioning`, `s3:PutBucketEncryption`
- `dynamodb:CreateTable`

### State Lock Stuck
If a lock is stuck after a failed apply:
```bash
terraform force-unlock LOCK_ID
```
