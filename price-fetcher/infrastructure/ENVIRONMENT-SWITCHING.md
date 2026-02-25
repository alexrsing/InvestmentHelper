# Environment Switching Guide

This guide explains how to safely switch between Terraform environments (dev, staging, prod).

## Available Environments

| Environment | Color | Script | Purpose |
|------------|-------|--------|---------|
| **dev** | Green | `./use-dev.sh` | Development and testing |
| **staging** | Yellow | `./use-staging.sh` | Pre-production validation |
| **prod** | Red | `./use-prod.sh` | Live production system |

## Color Coding

The scripts use colors to indicate environment risk level:

- **Green (dev)**: Safe for experimentation. Resources can be recreated.
- **Yellow (staging)**: Moderate caution. Data should be preserved.
- **Red (prod)**: High caution. Affects live systems.

## Switching Environments

### Check Current Environment

```bash
./current-env.sh
```

Output shows your active environment with color:
```
Current environment: DEV
```

### Switch to Development

```bash
./use-dev.sh
```

No confirmation required. Initializes Terraform with dev backend.

### Switch to Staging

```bash
./use-staging.sh
```

No confirmation required. Shows yellow warning.

### Switch to Production

```bash
./use-prod.sh
```

**Requires confirmation**: You must type `prod` to proceed.

```
=== PRODUCTION ENVIRONMENT ===

You are about to switch to the PRODUCTION environment.
This can affect live systems.

Type 'prod' to confirm: prod
```

## What Happens When You Switch

Each switch script:

1. Records the environment in `.current-env` file
2. Runs `terraform init -reconfigure` with the correct backend
3. Downloads the state file for that environment
4. Shows next steps

## Working After Switching

After switching, always use the correct tfvars file:

```bash
# After ./use-dev.sh
terraform plan -var-file=environments/dev/terraform.tfvars
terraform apply -var-file=environments/dev/terraform.tfvars

# After ./use-staging.sh
terraform plan -var-file=environments/staging/terraform.tfvars

# After ./use-prod.sh
terraform plan -var-file=environments/prod/terraform.tfvars
```

## Safety Features

### Production Confirmation

Production requires typing `prod` to confirm. This prevents accidental switches.

### Environment Tracking

The `.current-env` file tracks your active environment. The `current-env.sh` script reads this to show your current state.

### Separate State Files

Each environment has its own state file in S3:
- `price-fetcher/dev/terraform.tfstate`
- `price-fetcher/staging/terraform.tfstate`
- `price-fetcher/prod/terraform.tfstate`

## Common Mistakes

### Wrong tfvars File

**Problem**: Using dev tfvars while in prod environment.

```bash
# WRONG - will create dev-named resources in prod state
./use-prod.sh
terraform apply -var-file=environments/dev/terraform.tfvars
```

**Solution**: Always match tfvars to environment.

### Forgetting to Switch

**Problem**: Making changes in wrong environment.

**Solution**: Always run `./current-env.sh` before `terraform apply`.

### Applying Without Planning

**Problem**: Applying directly without reviewing changes.

```bash
# DANGEROUS
terraform apply -var-file=environments/prod/terraform.tfvars -auto-approve
```

**Solution**: Always run `terraform plan` first, especially in prod.

## Best Practices

1. **Start in dev**: Test all changes in dev first
2. **Check before apply**: Run `./current-env.sh` before any apply
3. **Plan before apply**: Never skip the plan step
4. **Review prod changes**: Have another team member review prod changes
5. **Use CI/CD for prod**: Let GitHub Actions deploy to prod
