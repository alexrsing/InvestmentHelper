#!/bin/bash
# Switch to PRODUCTION environment for Terraform operations
# Requires explicit confirmation due to production sensitivity
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.current-env"

# Red color for prod
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${RED}${BOLD}=== PRODUCTION ENVIRONMENT ===${NC}"
echo ""
echo -e "${RED}You are about to switch to the PRODUCTION environment.${NC}"
echo -e "${RED}This can affect live systems.${NC}"
echo ""
read -p "Type 'prod' to confirm: " confirmation

if [ "$confirmation" != "prod" ]; then
    echo "Aborted. Environment not changed."
    exit 1
fi

echo "prod" > "$ENV_FILE"

cd "$SCRIPT_DIR"
terraform init \
    -backend-config=environments/prod/backend-config.hcl \
    -reconfigure

echo ""
echo -e "${RED}${BOLD}NOW USING PRODUCTION ENVIRONMENT${NC}"
echo -e "${RED}Be careful with terraform apply!${NC}"
echo ""
echo "Next steps:"
echo "  terraform plan -var-file=environments/prod/terraform.tfvars"
echo "  terraform apply -var-file=environments/prod/terraform.tfvars"
