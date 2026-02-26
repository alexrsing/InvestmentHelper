#!/bin/bash
#
# Switch to PRODUCTION environment
#
# This script safely switches your Terraform backend to the production environment
# and provides a clear visual indicator of which environment you're using.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENV_NAME="prod"
ENV_COLOR="\033[0;31m"  # Red
RESET_COLOR="\033[0m"

echo -e "${ENV_COLOR}========================================${RESET_COLOR}"
echo -e "${ENV_COLOR}  Switching to: PRODUCTION environment${RESET_COLOR}"
echo -e "${ENV_COLOR}========================================${RESET_COLOR}"
echo ""
echo -e "${ENV_COLOR}⚠️  WARNING: You are about to work with PRODUCTION!${RESET_COLOR}"
echo ""
read -p "Are you sure you want to switch to production? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled. Staying in current environment."
    exit 1
fi

# Initialize with production backend
echo "Initializing Terraform with production backend..."
terraform init -reconfigure -backend-config=environments/prod/backend-config.hcl

# Save current environment to file
echo "$ENV_NAME" > .current-env

echo ""
echo -e "${ENV_COLOR}✓ Successfully switched to PRODUCTION environment${RESET_COLOR}"
echo ""
echo "S3 State Path: hedgeye-risk-tracker/prod/terraform.tfstate"
echo ""
echo -e "${ENV_COLOR}⚠️  DANGER: You are now working with PRODUCTION infrastructure!${RESET_COLOR}"
echo -e "${ENV_COLOR}   Double-check all changes before applying!${RESET_COLOR}"
echo ""
