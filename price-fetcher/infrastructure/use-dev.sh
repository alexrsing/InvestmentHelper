#!/bin/bash
# Switch to DEV environment for Terraform operations
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.current-env"

# Green color for dev
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Switching to DEV environment ===${NC}"
echo "dev" > "$ENV_FILE"

# Initialize Terraform with dev backend
cd "$SCRIPT_DIR"
terraform init \
    -backend-config=environments/dev/backend-config.hcl \
    -reconfigure

echo ""
echo -e "${GREEN}Now using DEV environment${NC}"
echo ""
echo "Next steps:"
echo "  terraform plan -var-file=environments/dev/terraform.tfvars"
echo "  terraform apply -var-file=environments/dev/terraform.tfvars"
