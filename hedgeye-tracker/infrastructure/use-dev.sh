#!/bin/bash
#
# Switch to DEV environment
#
# This script safely switches your Terraform backend to the dev environment
# and provides a clear visual indicator of which environment you're using.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENV_NAME="dev"
ENV_COLOR="\033[0;32m"  # Green
RESET_COLOR="\033[0m"

echo -e "${ENV_COLOR}========================================${RESET_COLOR}"
echo -e "${ENV_COLOR}  Switching to: DEV environment${RESET_COLOR}"
echo -e "${ENV_COLOR}========================================${RESET_COLOR}"
echo ""

# Initialize with dev backend
echo "Initializing Terraform with dev backend..."
terraform init -reconfigure -backend-config=environments/dev/backend-config.hcl

# Save current environment to file
echo "$ENV_NAME" > .current-env

echo ""
echo -e "${ENV_COLOR}✓ Successfully switched to DEV environment${RESET_COLOR}"
echo ""
echo "S3 State Path: hedgeye-risk-tracker/dev/terraform.tfstate"
echo ""
echo -e "${ENV_COLOR}WARNING: You are now working with DEV infrastructure${RESET_COLOR}"
echo ""
