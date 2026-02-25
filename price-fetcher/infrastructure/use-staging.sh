#!/bin/bash
# Switch to STAGING environment for Terraform operations
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.current-env"

# Yellow color for staging
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== Switching to STAGING environment ===${NC}"
echo "staging" > "$ENV_FILE"

cd "$SCRIPT_DIR"
terraform init \
    -backend-config=environments/staging/backend-config.hcl \
    -reconfigure

echo ""
echo -e "${YELLOW}Now using STAGING environment${NC}"
echo ""
echo "Next steps:"
echo "  terraform plan -var-file=environments/staging/terraform.tfvars"
echo "  terraform apply -var-file=environments/staging/terraform.tfvars"
