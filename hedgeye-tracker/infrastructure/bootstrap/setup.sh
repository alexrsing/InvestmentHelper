#!/bin/bash
#
# Bootstrap Script for Terraform S3 Backend
#
# This script creates the S3 bucket and DynamoDB table needed for
# Terraform remote state storage and locking.
#
# Usage:
#   ./setup.sh [org-name] [aws-region]
#
# Examples:
#   ./setup.sh                                    # Uses defaults
#   ./setup.sh hedgeye-risk-tracker us-west-2    # Custom values
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Terraform installed
#   - Permissions to create S3 buckets and DynamoDB tables

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
ORG_NAME="${1:-hedgeye-risk-tracker}"
AWS_REGION="${2:-us-west-2}"

echo -e "${GREEN}=== Terraform Backend Bootstrap ===${NC}"
echo "Organization: $ORG_NAME"
echo "AWS Region: $AWS_REGION"
echo ""

# Verify prerequisites
command -v terraform >/dev/null 2>&1 || {
    echo -e "${RED}Error: terraform is not installed${NC}" >&2
    exit 1
}

command -v aws >/dev/null 2>&1 || {
    echo -e "${RED}Error: AWS CLI is not installed${NC}" >&2
    exit 1
}

# Verify AWS credentials
aws sts get-caller-identity >/dev/null 2>&1 || {
    echo -e "${RED}Error: AWS credentials not configured${NC}" >&2
    exit 1
}

echo -e "${GREEN}✓ Prerequisites verified${NC}"
echo ""

# Initialize Terraform
echo -e "${YELLOW}Initializing Terraform...${NC}"
terraform init

# Plan the changes
echo -e "${YELLOW}Planning infrastructure...${NC}"
terraform plan \
    -var="org_name=$ORG_NAME" \
    -var="aws_region=$AWS_REGION" \
    -out=tfplan

# Prompt for confirmation
echo ""
echo -e "${YELLOW}Review the plan above.${NC}"
read -p "Do you want to apply these changes? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${RED}Aborted by user${NC}"
    rm -f tfplan
    exit 1
fi

# Apply the changes
echo -e "${YELLOW}Creating backend resources...${NC}"
terraform apply tfplan

# Clean up plan file
rm -f tfplan

# Get outputs
S3_BUCKET=$(terraform output -raw s3_bucket_name)
DYNAMODB_TABLE=$(terraform output -raw dynamodb_table_name)

echo ""
echo -e "${GREEN}=== Bootstrap Complete ===${NC}"
echo -e "${GREEN}✓ S3 Bucket: $S3_BUCKET${NC}"
echo -e "${GREEN}✓ DynamoDB Table: $DYNAMODB_TABLE${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Update backend-config.hcl files with bucket name: $S3_BUCKET"
echo "2. Navigate to main infrastructure directory"
echo "3. Initialize backend: terraform init -backend-config=environments/dev/backend-config.hcl"
echo "4. Migrate state: terraform init -migrate-state"
echo ""
echo -e "${GREEN}Backend resources are ready!${NC}"
