# Secrets Module

Creates a single AWS Secrets Manager JSON secret for all price fetcher API keys and configuration.

## Important

This module creates the secret **without a value**. The secret value must be set manually after deployment using the AWS CLI.

## Usage

```hcl
module "secrets" {
  source = "./modules/secrets"

  environment = "dev"
}
```

## Setting Secret Values

After deploying the infrastructure, set the JSON secret value:

```bash
aws secretsmanager put-secret-value \
  --secret-id dev/price-fetcher/config \
  --secret-string '{
    "ALPHA_VANTAGE_API_KEY": "your-key",
    "ALPHA_VANTAGE_TIER": "free",
    "TWELVEDATA_API_KEY": "your-key",
    "TWELVEDATA_TIER": "free",
    "FINNHUB_API_KEY": "your-key",
    "FINNHUB_TIER": "free",
    "FMP_API_KEY": "your-key",
    "FMP_TIER": "free"
  }'
```

Replace `dev` with the appropriate environment (`staging` or `prod`).

## Outputs

| Output | Description |
|--------|-------------|
| `config_secret_arn` | ARN for IAM policy |
| `config_secret_name` | Secret name for Lambda env var |
| `all_secret_arns` | List of all ARNs (for IAM module) |

## Security Features

- **No values in Terraform**: Secret values are never stored in state
- **30-day recovery window**: Protects against accidental deletion
- **KMS encryption**: Uses AWS managed keys by default
- **Environment isolation**: Separate secrets per environment

## Connecting to IAM Module

Pass the secret ARNs to the IAM module:

```hcl
module "iam" {
  source = "./modules/iam"

  environment         = "dev"
  dynamodb_table_arns = [...]
  secret_arns         = module.secrets.all_secret_arns
  log_group_arn       = aws_cloudwatch_log_group.lambda.arn
}
```
