#!/bin/bash
# Bootstrap Setup Script
# Creates S3 bucket and DynamoDB table for Terraform remote state management
#
# This is a ONE-TIME setup. Only run this once per AWS account.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Price Fetcher Terraform Bootstrap ===${NC}"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}Error: Terraform is not installed${NC}"
    echo "Install from: https://developer.hashicorp.com/terraform/install"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    echo "Install from: https://aws.amazon.com/cli/"
    exit 1
fi

# Verify AWS credentials
echo "Verifying AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials not configured${NC}"
    echo "Run: aws configure"
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-west-2")
echo -e "AWS Account: ${GREEN}${AWS_ACCOUNT_ID}${NC}"
echo -e "AWS Region: ${GREEN}${AWS_REGION}${NC}"
echo ""

# Confirm before proceeding
echo -e "${YELLOW}This will create:${NC}"
echo "  - S3 bucket: price-fetcher-terraform-state"
echo "  - DynamoDB table: price-fetcher-terraform-lock"
echo ""
read -p "Continue? (y/N): " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Initializing Terraform..."
cd "$SCRIPT_DIR"
terraform init

echo ""
echo "Planning infrastructure..."
terraform plan -out=bootstrap.tfplan

echo ""
read -p "Apply this plan? (y/N): " apply_confirm
if [[ ! "$apply_confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted. Plan saved to bootstrap.tfplan"
    exit 0
fi

echo ""
echo "Applying infrastructure..."
terraform apply bootstrap.tfplan

echo ""
echo -e "${GREEN}=== Bootstrap Complete ===${NC}"
echo ""
echo "Next steps:"
echo "1. Copy the backend configuration from the output above"
echo "2. Create infrastructure/backend.tf with that configuration"
echo "3. Run 'terraform init' in the infrastructure/ directory"
echo ""
echo "For detailed instructions, see README.md"
