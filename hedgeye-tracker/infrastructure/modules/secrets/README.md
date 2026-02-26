# Secrets Manager Module

This module creates AWS Secrets Manager secrets for securely storing sensitive credentials used by the Hedgeye Risk Tracker application.

## Secrets Created

- **Gmail Service Account** (`{environment}/hedgeye/gmail-service-account`)
  - Stores Gmail API service account JSON credentials
  - Used for domain-wide delegation to access Gmail

## Important: Secret Values

**Secret values are NOT managed by Terraform.** This is a security best practice to keep sensitive data out of Terraform state files.

### Setting Secret Values

After Terraform creates the secret, you must manually set the value:

#### Using AWS CLI

```bash
# Set Gmail service account secret
aws secretsmanager put-secret-value \
  --secret-id dev/hedgeye/gmail-service-account \
  --secret-string file://service-account.json
```

#### Using AWS Console

1. Navigate to AWS Secrets Manager
2. Find the secret: `{environment}/hedgeye/gmail-service-account`
3. Click "Retrieve secret value"
4. Click "Edit"
5. Paste the service account JSON
6. Click "Save"

### Retrieving Secret Values

```bash
# Get secret value
aws secretsmanager get-secret-value \
  --secret-id dev/hedgeye/gmail-service-account \
  --query SecretString \
  --output text
```

## Module Usage

```hcl
module "secrets" {
  source = "./modules/secrets"

  environment           = "dev"
  recovery_window_days  = 30
  enable_rotation      = false

  tags = {
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| environment | Environment name (dev, staging, prod) | string | - | yes |
| recovery_window_days | Days to retain secret after deletion (7-30) | number | 30 | no |
| enable_rotation | Enable automatic secret rotation | bool | false | no |
| rotation_days | Days between automatic rotations | number | 30 | no |
| tags | Common tags to apply to secrets | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| gmail_secret_arn | ARN of the Gmail service account secret |
| gmail_secret_name | Name of the Gmail service account secret |
| gmail_secret_id | Unique identifier of the secret |

## Security Features

✅ **KMS Encryption** - All secrets encrypted with AWS managed key
✅ **Recovery Window** - 30-day recovery period for accidental deletion
✅ **Environment Isolation** - Separate secrets per environment
✅ **IAM Controlled** - Access restricted to application execution role
✅ **CloudTrail Logged** - All secret access events logged

## Secret Rotation

Service account keys typically don't require automatic rotation. If you need to rotate:

1. **Manual Rotation** (Recommended):
   ```bash
   # Generate new service account key in Google Cloud Console
   # Update secret value
   aws secretsmanager put-secret-value \
     --secret-id dev/hedgeye/gmail-service-account \
     --secret-string file://new-service-account.json
   ```

2. **Automatic Rotation** (Advanced):
   - Set `enable_rotation = true`
   - Requires Lambda function to perform rotation
   - See AWS documentation for implementation

## Emergency Access

If you need to access secrets in an emergency:

```bash
# List all secrets
aws secretsmanager list-secrets

# Get specific secret
aws secretsmanager get-secret-value \
  --secret-id {environment}/hedgeye/gmail-service-account

# Update secret in emergency
aws secretsmanager update-secret \
  --secret-id {environment}/hedgeye/gmail-service-account \
  --description "Emergency update on $(date)"

aws secretsmanager put-secret-value \
  --secret-id {environment}/hedgeye/gmail-service-account \
  --secret-string file://backup-service-account.json
```

## Deletion and Recovery

```bash
# Delete secret (enters recovery window)
aws secretsmanager delete-secret \
  --secret-id dev/hedgeye/gmail-service-account \
  --recovery-window-in-days 30

# Restore deleted secret (within recovery window)
aws secretsmanager restore-secret \
  --secret-id dev/hedgeye/gmail-service-account

# Force immediate deletion (DANGEROUS - no recovery)
aws secretsmanager delete-secret \
  --secret-id dev/hedgeye/gmail-service-account \
  --force-delete-without-recovery
```

## Migration from Environment Variables

1. ✅ Create secret via Terraform
2. ✅ Set secret value using AWS CLI or Console
3. ⏳ Update application code to read from Secrets Manager (Issue #2)
4. ⏳ Test in dev environment
5. ⏳ Deploy to staging/prod
6. ⏳ Remove `GMAIL_APP_DETAILS` from `.env` files
7. ⏳ Revoke old service account keys (if rotating)
