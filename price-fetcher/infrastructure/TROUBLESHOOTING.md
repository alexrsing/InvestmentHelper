# Troubleshooting Guide

Common issues and solutions for the price-fetcher infrastructure.

## Terraform State Issues

### State Lock Stuck

**Symptoms**:
```
Error: Error acquiring the state lock
Lock Info:
  ID:        xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Path:      price-fetcher/dev/terraform.tfstate
```

**Cause**: Previous terraform run crashed or was interrupted.

**Solution**:
```bash
# Force unlock with the Lock ID from error message
terraform force-unlock xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### State File Not Found

**Symptoms**:
```
Error: Failed to get existing workspaces
```

**Cause**: Backend not initialized or wrong environment.

**Solution**:
```bash
# Reinitialize with correct backend
./use-dev.sh  # or appropriate environment
```

### State Drift

**Symptoms**: Plan shows unexpected changes to resources that weren't modified.

**Cause**: Manual changes made outside Terraform.

**Solution**:
```bash
# Import existing resource or refresh state
terraform refresh -var-file=environments/dev/terraform.tfvars

# Or import specific resource
terraform import module.lambda[0].aws_lambda_function.price_fetcher dev-price-fetcher
```

## Lambda Issues

### Lambda Invocation Fails

**Symptoms**:
```json
{"errorMessage": "Unable to import module 'lambda_handler'"}
```

**Cause**: Deployment package missing files or wrong structure.

**Solution**:
```bash
# Rebuild package
cd deployment
./package-lambda.sh

# Redeploy
aws lambda update-function-code \
  --function-name dev-price-fetcher \
  --zip-file fileb://build/lambda.zip
```

### Lambda Timeout

**Symptoms**: Function times out before completing.

**Cause**: Too many symbols or slow API responses.

**Solution**:
- Reduce `max_symbols_per_run` in tfvars
- Check API rate limits
- Consider increasing timeout (max 900s)

### Import Error for Dependencies

**Symptoms**:
```
Runtime.ImportModuleError: Unable to import module 'lambda_handler': No module named 'boto3'
```

**Cause**: Dependencies installed for wrong platform.

**Solution**:
```bash
# Ensure package script installs for Linux
./package-lambda.sh  # Uses --platform manylinux2014_x86_64
```

## Secrets Manager Issues

### Secret Not Found

**Symptoms**:
```
botocore.exceptions.ClientError: ResourceNotFoundException: Secrets Manager can't find the specified secret.
```

**Cause**: Secret not created or wrong name.

**Solution**:
```bash
# List secrets to verify name
aws secretsmanager list-secrets --query 'SecretList[*].Name'

# Create if missing
terraform apply -var-file=environments/dev/terraform.tfvars
```

### Secret Value Not Set

**Symptoms**: Lambda returns null for API key.

**Cause**: Secret created but no value set.

**Solution**:
```bash
# Set the secret value
aws secretsmanager put-secret-value \
  --secret-id dev/price-fetcher/alpha-vantage-api-key \
  --secret-string "YOUR_API_KEY"
```

## IAM Issues

### Access Denied to DynamoDB

**Symptoms**:
```
AccessDeniedException: User: arn:aws:sts::...:assumed-role/dev-price-fetcher-execution-role/...
is not authorized to perform: dynamodb:PutItem
```

**Cause**: Table name doesn't match IAM policy pattern.

**Solution**:
- Check table name starts with environment prefix (e.g., `dev-`)
- Verify IAM policy in `modules/iam/main.tf`

### OIDC Authentication Failed

**Symptoms** (in GitHub Actions):
```
Error: Could not assume role with OIDC
```

**Cause**: Trust policy doesn't allow repository/branch.

**Solution**:
1. Check `github_org` and `github_repo` in tfvars
2. Verify OIDC provider exists:
   ```bash
   aws iam list-open-id-connect-providers
   ```
3. Check role trust policy allows your repository

## Scheduler Issues

### Events Not Triggering

**Symptoms**: Lambda not invoked on schedule.

**Cause**: EventBridge rule disabled or wrong target.

**Solution**:
```bash
# Check rule status
aws events describe-rule --name dev-price-fetcher-schedule

# Check targets
aws events list-targets-by-rule --rule dev-price-fetcher-schedule

# Enable if disabled
aws events enable-rule --name dev-price-fetcher-schedule
```

### Wrong Schedule Time

**Symptoms**: Lambda runs at unexpected times.

**Cause**: Cron expression in UTC, not local time.

**Solution**:
- All schedules are in UTC
- US market hours (9:30 AM - 4:00 PM ET) = 14:30 - 21:00 UTC
- Update `price_fetcher_schedule` in tfvars if needed

## Monitoring Issues

### Alarms Not Triggering

**Symptoms**: Errors occur but no notifications.

**Cause**: SNS subscription not confirmed.

**Solution**:
1. Check email for subscription confirmation
2. Verify email address in `monitoring_alert_email`
3. Check SNS subscription status:
   ```bash
   aws sns list-subscriptions-by-topic --topic-arn <topic-arn>
   ```

### Too Many Alerts

**Symptoms**: Alert fatigue from frequent alarms.

**Solution**:
- Adjust alarm thresholds in `modules/monitoring/main.tf`
- Consider longer evaluation periods
- Filter out expected errors

## Bootstrap Issues

### Bucket Already Exists

**Symptoms**:
```
Error: creating S3 Bucket: BucketAlreadyOwnedByYou
```

**Cause**: Bucket exists (possibly from previous setup).

**Solution**:
```bash
# Import existing bucket
cd bootstrap
terraform import aws_s3_bucket.terraform_state price-fetcher-terraform-state
terraform apply
```

### DynamoDB Table Exists

**Symptoms**:
```
Error: creating DynamoDB Table: ResourceInUseException
```

**Solution**:
```bash
terraform import aws_dynamodb_table.terraform_lock price-fetcher-terraform-lock
terraform apply
```

## Getting Help

1. Check CloudWatch Logs for Lambda errors
2. Review Terraform plan output carefully
3. Use AWS Console to verify resource state
4. Check AWS Service Health Dashboard for outages
