# GitHub Actions OIDC Module

This module sets up OpenID Connect (OIDC) authentication between GitHub Actions and AWS, enabling secure, credential-free deployments.

## Features

- **OIDC Identity Provider**: Creates the AWS IAM OIDC provider for GitHub Actions
- **IAM Role**: Creates a role that GitHub Actions workflows can assume
- **Least-Privilege Policies**: Separate policies for different resource types
- **Repository Restriction**: Trust policy limits access to specific GitHub repository

## Benefits

- No long-lived AWS credentials stored in GitHub Secrets
- Automatically rotated temporary credentials
- Fine-grained permissions per resource type
- AWS security best practice
- Full CloudTrail audit trail

## Usage

```hcl
module "github_oidc" {
  source = "./modules/github-oidc"

  environment            = "dev"
  aws_region             = "us-west-2"
  aws_account_id         = "123456789012"
  github_repository      = "myorg/myrepo"
  terraform_state_bucket = "my-terraform-state"
  terraform_lock_table   = "terraform-locks"

  tags = {
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
```

## GitHub Actions Workflow Usage

Once deployed, use in workflows like this:

```yaml
name: Deploy

on:
  push:
    branches: [main]

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/dev-github-actions-deployment
          aws-region: us-west-2

      - name: Verify AWS Access
        run: aws sts get-caller-identity
```

## Policies

The module creates the following IAM policies:

| Policy | Purpose |
|--------|---------|
| `terraform_state` | Access to S3 state bucket and DynamoDB lock table |
| `infrastructure` | Manage DynamoDB tables, Secrets Manager, IAM roles |
| `lambda_deployment` | Deploy Lambda functions, manage CloudWatch Logs |
| `monitoring` | Create SNS topics and CloudWatch alarms |
| `sts_read` | Verify caller identity |

## Security Considerations

1. **Repository Restriction**: The trust policy only allows the specified GitHub repository to assume the role
2. **Audience Validation**: Requires `sts.amazonaws.com` as the token audience
3. **Resource Restrictions**: Policies limit access to resources matching `*hedgeye*` pattern
4. **No Wildcard Actions**: Actions are explicitly listed, not wildcarded

## Inputs

| Name | Description | Type | Required |
|------|-------------|------|----------|
| `environment` | Environment name | `string` | Yes |
| `aws_region` | AWS region | `string` | Yes |
| `aws_account_id` | AWS account ID | `string` | Yes |
| `github_repository` | GitHub repo (owner/repo) | `string` | Yes |
| `terraform_state_bucket` | S3 bucket for TF state | `string` | Yes |
| `terraform_lock_table` | DynamoDB lock table | `string` | Yes |
| `tags` | Resource tags | `map(string)` | No |

## Outputs

| Name | Description |
|------|-------------|
| `oidc_provider_arn` | ARN of the OIDC provider |
| `role_arn` | ARN of the GitHub Actions IAM role |
| `role_name` | Name of the IAM role |
| `policy_arns` | Map of all attached policy ARNs |

## Troubleshooting

### "Not authorized to perform sts:AssumeRoleWithWebIdentity"

- Verify the `github_repository` variable matches exactly (case-sensitive)
- Check the workflow has `permissions: id-token: write`

### "Invalid identity token"

- The OIDC thumbprint may have changed; check GitHub's documentation
- Ensure the OIDC provider URL is correct

### "Access Denied" on specific operation

- Check the policy allows the action on the specific resource
- Verify resource names match the `*hedgeye*` pattern
