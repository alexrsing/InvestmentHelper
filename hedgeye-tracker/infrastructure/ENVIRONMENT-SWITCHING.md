# Safe Environment Switching Guide

This guide shows you the **easy and safe** way to switch between dev, staging, and production environments.

## The Problem We Solved

The original approach was error-prone:
```bash
# ❌ Easy to make mistakes
terraform init -reconfigure -backend-config=environments/staging/backend-config.hcl
```

Problems:
- Long, complex command
- Easy to forget which environment you're in
- No visual indicator
- Risk of accidentally modifying the wrong environment

## The Solution

Simple shell scripts that make environment switching **safe and obvious**.

---

## Quick Start

```bash
cd infrastructure

# Switch to dev
./use-dev.sh

# Switch to staging
./use-staging.sh

# Switch to production (requires confirmation)
./use-prod.sh

# Check current environment
./current-env.sh
```

---

## How It Works

### Environment Switcher Scripts

Each script:
- ✅ Runs the correct `terraform init` command
- ✅ Saves the current environment to `.current-env`
- ✅ Shows clear visual feedback with colors
- ✅ Production requires confirmation

**Colors:**
- 🟢 **DEV**: Green
- 🟡 **STAGING**: Yellow
- 🔴 **PROD**: Red (with extra warnings)

### Current Environment Tracking

The `.current-env` file tracks which environment you're using:
- Created automatically by the switch scripts
- Lets you check which environment is active
- Ignored by git (local to your machine)

### Safety Features

**Production Protection:**
```bash
./use-prod.sh
# ⚠️  WARNING: You are about to work with PRODUCTION!
# Are you sure you want to switch to production? (yes/no):
```

**Visual Confirmation:**
Every script shows clear output about which environment you're now using.

---

## Complete Workflow Examples

### Example 1: Working with Dev

```bash
cd infrastructure

# Switch to dev
./use-dev.sh
# ========================================
#   Switching to: DEV environment
# ========================================
# ✓ Successfully switched to DEV environment

# Check what would change
terraform plan

# Apply changes
terraform apply
```

### Example 2: Deploying to Staging

```bash
cd infrastructure

# Switch to staging
./use-staging.sh
# ========================================
#   Switching to: STAGING environment
# ========================================
# ✓ Successfully switched to STAGING environment

# Verify current environment
./current-env.sh
# Current environment: STAGING

# Preview changes
terraform plan

# Apply if looks good
terraform apply
```

### Example 3: Production Deployment

```bash
cd infrastructure

# Switch to production (requires confirmation)
./use-prod.sh
# ========================================
#   Switching to: PRODUCTION environment
# ========================================
# ⚠️  WARNING: You are about to work with PRODUCTION!
# Are you sure you want to switch to production? (yes/no): yes
# ⚠️  DANGER: You are now working with PRODUCTION infrastructure!

# Double-check environment
./current-env.sh
# Current environment: PROD

# Review changes carefully
terraform plan

# Apply with extra caution
terraform apply
```

---

## Visual Indicators

### Script Output (Color-coded)

**Dev (Green):**
```
========================================
  Switching to: DEV environment
========================================

✓ Successfully switched to DEV environment

S3 State Path: hedgeye-risk-tracker/dev/terraform.tfstate

WARNING: You are now working with DEV infrastructure
```

**Staging (Yellow):**
```
========================================
  Switching to: STAGING environment
========================================

✓ Successfully switched to STAGING environment

S3 State Path: hedgeye-risk-tracker/staging/terraform.tfstate

WARNING: You are now working with STAGING infrastructure
```

**Production (Red):**
```
========================================
  Switching to: PRODUCTION environment
========================================

⚠️  WARNING: You are about to work with PRODUCTION!

Are you sure you want to switch to production? (yes/no): yes

✓ Successfully switched to PRODUCTION environment

S3 State Path: hedgeye-risk-tracker/prod/terraform.tfstate

⚠️  DANGER: You are now working with PRODUCTION infrastructure!
   Double-check all changes before applying!
```

---

## Best Practices

### 1. Always Check Current Environment

Before any operation:
```bash
./current-env.sh
```

Or combine with terraform commands:
```bash
./current-env.sh && terraform plan
./current-env.sh && terraform apply
```

### 2. Use Scripts, Not Manual Commands

❌ **Don't do this:**
```bash
terraform init -reconfigure -backend-config=environments/staging/backend-config.hcl
```

✅ **Do this:**
```bash
./use-staging.sh
```

### 3. Be Explicit When Switching

When switching environments, say it out loud:
- "Switching to dev"
- "Now working in staging"
- "Moving to production"

This mental acknowledgment reduces mistakes.

### 4. Production Checklist

Before applying changes to production:
- [ ] Tested in dev
- [ ] Tested in staging
- [ ] Reviewed `terraform plan` output
- [ ] Confirmed with team
- [ ] Verified current environment: `./current-env.sh`
- [ ] Ready to apply

---

## Available Scripts

### Environment Switchers

**`./use-dev.sh`**
- Switches to dev environment
- Shows green output
- Updates `.current-env` file

**`./use-staging.sh`**
- Switches to staging environment
- Shows yellow output
- Updates `.current-env` file

**`./use-prod.sh`**
- Switches to production environment
- Shows red output with warnings
- Requires confirmation ("yes")
- Updates `.current-env` file

**`./current-env.sh`**
- Shows which environment you're currently using
- Color-coded output (green/yellow/red)
- Exits with error if no environment selected

---

## Troubleshooting

### "No environment selected" Error

**Problem:**
```bash
./current-env.sh
# ⚠️  No environment selected
```

**Solution:**
Switch to an environment first:
```bash
./use-dev.sh
```

### Forgot Which Environment You're In

**Check it:**
```bash
./current-env.sh
# Current environment: DEV
```

### Need to Switch Quickly

**Just run the script:**
```bash
./use-dev.sh      # Fast and clear
```

### Production Won't Let You Switch

This is intentional! Production requires confirmation:
```bash
./use-prod.sh
# Are you sure you want to switch to production? (yes/no): yes
```

---

## What Happens Behind the Scenes

When you run `./use-dev.sh`:

1. Script runs initialization:
   ```bash
   terraform init -reconfigure -backend-config=environments/dev/backend-config.hcl
   ```

2. Environment saved to file:
   ```bash
   echo "dev" > .current-env
   ```

3. Confirmation message displayed:
   ```
   ✓ Successfully switched to DEV environment
   ```

When you run `./current-env.sh`:

1. Reads the `.current-env` file
2. Displays environment name with appropriate color
3. If file doesn't exist, shows error and instructions

---

## Comparison

### Old Way ❌

```bash
# Complex, error-prone
terraform init -reconfigure -backend-config=environments/staging/backend-config.hcl
terraform plan
terraform apply

# No idea which environment you're in
# No confirmation prompts
# No visual indicators
```

### New Way ✅

```bash
# Clear and safe
./use-staging.sh
# ✓ Successfully switched to STAGING environment

./current-env.sh
# Current environment: STAGING

terraform plan
terraform apply
```

---

## Integration with Your Workflow

### Adding to Your Shell Prompt (Optional)

You can add the current environment to your shell prompt:

**Bash (~/.bashrc):**
```bash
# Add to PS1
tf_env() {
  if [ -f infrastructure/.current-env ]; then
    echo "[$(cat infrastructure/.current-env)]"
  fi
}
PS1='$(tf_env) \u@\h:\w\$ '
```

**Result:**
```
[dev] user@host:~/project/infrastructure$
```

### Alias Shortcuts (Optional)

Add these to your `~/.bashrc` or `~/.zshrc`:

```bash
alias tfdev='cd ~/project/infrastructure && ./use-dev.sh'
alias tfstaging='cd ~/project/infrastructure && ./use-staging.sh'
alias tfprod='cd ~/project/infrastructure && ./use-prod.sh'
alias tfenv='cd ~/project/infrastructure && ./current-env.sh'
```

Then from anywhere:
```bash
tfdev        # Switch to dev
tfenv        # Check environment
```

---

## Summary

✅ **Environment switching is now:**
- Simple: `./use-dev.sh`, `./use-staging.sh`, `./use-prod.sh`
- Safe: Color-coded, confirmations, visual indicators
- Obvious: Always know which environment you're in
- Self-documenting: Clear script names

✅ **You can't accidentally:**
- Work in the wrong environment
- Apply changes without knowing which environment
- Forget which environment is active

✅ **Best practices enforced:**
- Production requires explicit confirmation
- Current environment clearly indicated
- Simple, standard shell scripts (no dependencies)

---

## Script Details

All scripts are simple bash scripts that:
- Use standard bash features (no special dependencies)
- Are executable (`chmod +x` already applied)
- Have clear, descriptive names
- Include comments explaining what they do
- Follow consistent patterns

You can read any script to see exactly what it does:
```bash
cat use-dev.sh
```

---

## Next Steps

Start using the new workflow:

```bash
cd infrastructure
./use-dev.sh      # Switch to dev
./current-env.sh  # Verify
terraform plan    # Start working!
```

Remember: These are just simple shell scripts. No magic, no dependencies, just straightforward automation of the Terraform backend switching process.
