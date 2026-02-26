#!/bin/bash
#
# Display current Terraform environment
#
# Shows which environment you're currently working with

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .current-env ]; then
    echo "⚠️  No environment selected"
    echo ""
    echo "Please run one of:"
    echo "  ./use-dev.sh"
    echo "  ./use-staging.sh"
    echo "  ./use-prod.sh"
    exit 1
fi

ENV_NAME=$(cat .current-env)

case "$ENV_NAME" in
    dev)
        ENV_COLOR="\033[0;32m"  # Green
        ;;
    staging)
        ENV_COLOR="\033[0;33m"  # Yellow
        ;;
    prod)
        ENV_COLOR="\033[0;31m"  # Red
        ;;
    *)
        ENV_COLOR="\033[0m"
        ;;
esac

RESET_COLOR="\033[0m"

echo -e "${ENV_COLOR}Current environment: ${ENV_NAME^^}${RESET_COLOR}"
