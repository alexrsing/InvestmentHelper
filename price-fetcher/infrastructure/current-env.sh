#!/bin/bash
# Display the currently selected Terraform environment
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.current-env"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

if [ ! -f "$ENV_FILE" ]; then
    echo "No environment selected."
    echo ""
    echo "Run one of:"
    echo "  ./use-dev.sh     - Development environment"
    echo "  ./use-staging.sh - Staging environment"
    echo "  ./use-prod.sh    - Production environment"
    exit 1
fi

CURRENT_ENV=$(cat "$ENV_FILE")

case "$CURRENT_ENV" in
    dev)
        echo -e "Current environment: ${GREEN}${BOLD}DEV${NC}"
        echo ""
        echo "To deploy:"
        echo "  terraform plan -var-file=environments/dev/terraform.tfvars"
        echo "  terraform apply -var-file=environments/dev/terraform.tfvars"
        ;;
    staging)
        echo -e "Current environment: ${YELLOW}${BOLD}STAGING${NC}"
        echo ""
        echo "To deploy:"
        echo "  terraform plan -var-file=environments/staging/terraform.tfvars"
        echo "  terraform apply -var-file=environments/staging/terraform.tfvars"
        ;;
    prod)
        echo -e "Current environment: ${RED}${BOLD}PRODUCTION${NC}"
        echo ""
        echo "To deploy (with caution):"
        echo "  terraform plan -var-file=environments/prod/terraform.tfvars"
        echo "  terraform apply -var-file=environments/prod/terraform.tfvars"
        ;;
    *)
        echo "Unknown environment: $CURRENT_ENV"
        exit 1
        ;;
esac
