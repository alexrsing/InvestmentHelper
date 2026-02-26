#!/bin/bash
#
# Manual Bootstrap Script for Terraform Backend (AWS CLI)
#
# This script creates the S3 bucket and DynamoDB table using AWS CLI
# instead of Terraform. Use this if you don't have Terraform permissions
# but have AWS CLI permissions.
#
# Usage:
#   ./manual-setup.sh
#
# Prerequisites:
#   - AWS CLI configured with credentials that have S3 and DynamoDB permissions
#   - Permissions: s3:CreateBucket, dynamodb:CreateTable, etc.

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BUCKET_NAME="hedgeye-risk-tracker-terraform-state"
TABLE_NAME="terraform-state-lock"
AWS_REGION="us-west-2"

echo -e "${GREEN}=== Manual Terraform Backend Bootstrap ===${NC}"
echo "Bucket: $BUCKET_NAME"
echo "Table: $TABLE_NAME"
echo "Region: $AWS_REGION"
echo ""

# Verify AWS credentials
aws sts get-caller-identity >/dev/null 2>&1 || {
    echo -e "${RED}Error: AWS credentials not configured${NC}" >&2
    exit 1
}

echo -e "${GREEN}✓ AWS credentials verified${NC}"
echo ""

# Create S3 bucket
echo -e "${YELLOW}Creating S3 bucket...${NC}"
if aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
    echo -e "${YELLOW}Bucket already exists: $BUCKET_NAME${NC}"
else
    aws s3api create-bucket \
        --bucket "$BUCKET_NAME" \
        --region "$AWS_REGION" \
        --create-bucket-configuration LocationConstraint="$AWS_REGION"
    echo -e "${GREEN}✓ S3 bucket created${NC}"
fi

# Enable versioning
echo -e "${YELLOW}Enabling bucket versioning...${NC}"
aws s3api put-bucket-versioning \
    --bucket "$BUCKET_NAME" \
    --versioning-configuration Status=Enabled
echo -e "${GREEN}✓ Versioning enabled${NC}"

# Enable encryption
echo -e "${YELLOW}Enabling server-side encryption...${NC}"
aws s3api put-bucket-encryption \
    --bucket "$BUCKET_NAME" \
    --server-side-encryption-configuration '{
        "Rules": [{
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "AES256"
            }
        }]
    }'
echo -e "${GREEN}✓ Encryption enabled${NC}"

# Block public access
echo -e "${YELLOW}Blocking public access...${NC}"
aws s3api put-public-access-block \
    --bucket "$BUCKET_NAME" \
    --public-access-block-configuration \
        BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
echo -e "${GREEN}✓ Public access blocked${NC}"

# Add lifecycle policy
echo -e "${YELLOW}Configuring lifecycle policy...${NC}"
cat > /tmp/lifecycle-policy.json <<EOF
{
    "Rules": [
        {
            "Id": "expire-old-versions",
            "Status": "Enabled",
            "Filter": {},
            "NoncurrentVersionExpiration": {
                "NoncurrentDays": 90
            }
        },
        {
            "Id": "abort-incomplete-uploads",
            "Status": "Enabled",
            "Filter": {},
            "AbortIncompleteMultipartUpload": {
                "DaysAfterInitiation": 7
            }
        }
    ]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
    --bucket "$BUCKET_NAME" \
    --lifecycle-configuration file:///tmp/lifecycle-policy.json
rm /tmp/lifecycle-policy.json
echo -e "${GREEN}✓ Lifecycle policy configured${NC}"

# Add tags
echo -e "${YELLOW}Adding bucket tags...${NC}"
aws s3api put-bucket-tagging \
    --bucket "$BUCKET_NAME" \
    --tagging 'TagSet=[
        {Key=Name,Value=Terraform State Bucket},
        {Key=Purpose,Value=terraform-state-storage},
        {Key=ManagedBy,Value=terraform-bootstrap},
        {Key=Environment,Value=shared}
    ]'
echo -e "${GREEN}✓ Tags added${NC}"

# Create DynamoDB table
echo -e "${YELLOW}Creating DynamoDB table...${NC}"
if aws dynamodb describe-table --table-name "$TABLE_NAME" --region "$AWS_REGION" 2>/dev/null; then
    echo -e "${YELLOW}Table already exists: $TABLE_NAME${NC}"
else
    aws dynamodb create-table \
        --table-name "$TABLE_NAME" \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region "$AWS_REGION" \
        --tags Key=Name,Value="Terraform State Lock Table" \
               Key=Purpose,Value=terraform-state-locking \
               Key=ManagedBy,Value=terraform-bootstrap \
               Key=Environment,Value=shared

    echo -e "${YELLOW}Waiting for table to be active...${NC}"
    aws dynamodb wait table-exists --table-name "$TABLE_NAME" --region "$AWS_REGION"
    echo -e "${GREEN}✓ DynamoDB table created${NC}"
fi

# Enable point-in-time recovery
echo -e "${YELLOW}Enabling point-in-time recovery...${NC}"
aws dynamodb update-continuous-backups \
    --table-name "$TABLE_NAME" \
    --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
    --region "$AWS_REGION"
echo -e "${GREEN}✓ Point-in-time recovery enabled${NC}"

echo ""
echo -e "${GREEN}=== Bootstrap Complete ===${NC}"
echo -e "${GREEN}✓ S3 Bucket: $BUCKET_NAME${NC}"
echo -e "${GREEN}✓ DynamoDB Table: $TABLE_NAME${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Navigate to main infrastructure directory: cd .."
echo "2. Initialize backend: terraform init -backend-config=environments/dev/backend-config.hcl"
echo "3. Migrate state: terraform init -migrate-state"
echo ""
echo -e "${GREEN}Backend resources are ready!${NC}"
