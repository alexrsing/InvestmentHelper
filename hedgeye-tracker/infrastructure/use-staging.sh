#!/bin/bash
#
# Switch to STAGING environment
#
# This script safely switches your Terraform backend to the staging environment
# and provides a clear visual indicator of which environment you're using.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENV_NAME="staging"
ENV_COLOR="\033[0;33m"  # Yellow
RESET_COLOR="\033[0m"

echo -e "${ENV_COLOR}========================================${RESET_COLOR}"
echo -e "${ENV_COLOR}  Switching to: STAGING environment${RESET_COLOR}"
echo -e "${ENV_COLOR}========================================${RESET_COLOR}"
echo ""

# Initialize with staging backend
echo "Initializing Terraform with staging backend..."
terraform init -reconfigure -backend-config=environments/staging/backend-config.hcl

# Save current environment to file
echo "$ENV_NAME" > .current-env

echo ""
echo -e "${ENV_COLOR}✓ Successfully switched to STAGING environment${RESET_COLOR}"
echo ""
echo "S3 State Path: hedgeye-risk-tracker/staging/terraform.tfstate"
echo ""
echo -e "${ENV_COLOR}WARNING: You are now working with STAGING infrastructure${RESET_COLOR}"
echo ""
