#!/bin/bash
# Lambda Package Builder
# Creates a deployable zip file with dependencies for AWS Lambda
#
# Usage: ./deployment/package-lambda.sh
# Output: deployment/build/lambda.zip

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$SCRIPT_DIR/build"
PACKAGE_DIR="$BUILD_DIR/package"
OUTPUT_FILE="$BUILD_DIR/lambda.zip"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Lambda Package Builder ===${NC}"
echo "Project root: $PROJECT_ROOT"
echo ""

# Clean previous build
echo "Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$PACKAGE_DIR"

# Install dependencies to package directory
# Uses requirements-lambda.txt (excludes yfinance/numpy/pandas for smaller package)
echo -e "${GREEN}Installing dependencies...${NC}"
pip install -r "$PROJECT_ROOT/requirements-lambda.txt" \
    -t "$PACKAGE_DIR" \
    --upgrade \
    --quiet

# Copy application code
echo -e "${GREEN}Copying application code...${NC}"

# Copy fetchers package
cp -r "$PROJECT_ROOT/fetchers" "$PACKAGE_DIR/"

# Copy pricedata package
mkdir -p "$PACKAGE_DIR/pricedata"
cp -r "$PROJECT_ROOT/src/pricedata"/* "$PACKAGE_DIR/pricedata/"

# Copy scripts (for holiday and validator handlers)
cp -r "$PROJECT_ROOT/scripts" "$PACKAGE_DIR/"

# Copy config directory if exists
if [ -d "$PROJECT_ROOT/config" ]; then
    cp -r "$PROJECT_ROOT/config" "$PACKAGE_DIR/"
fi

# Copy Lambda handler
cp "$PROJECT_ROOT/lambda_handler.py" "$PACKAGE_DIR/"

# Remove unnecessary files to reduce size
echo -e "${GREEN}Cleaning up package...${NC}"
find "$PACKAGE_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -name "*.pyc" -delete 2>/dev/null || true
find "$PACKAGE_DIR" -name "*.pyo" -delete 2>/dev/null || true

# Remove boto3/botocore (already in Lambda runtime)
rm -rf "$PACKAGE_DIR/boto3" "$PACKAGE_DIR/botocore" 2>/dev/null || true

# Create zip file
echo -e "${GREEN}Creating zip package...${NC}"
cd "$PACKAGE_DIR"
zip -r "$OUTPUT_FILE" . -x "*.pyc" -x "__pycache__/*" -q

# Report size
SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
UNZIPPED_SIZE=$(du -sm "$PACKAGE_DIR" | cut -f1)

echo ""
echo -e "${GREEN}=== Package Complete ===${NC}"
echo "Output: $OUTPUT_FILE"
echo "Zipped size: $SIZE"
echo "Unzipped size: ${UNZIPPED_SIZE} MB"
echo ""

# Warn if package is too large
if [ "$UNZIPPED_SIZE" -gt 250 ]; then
    echo -e "${RED}WARNING: Unzipped size ($UNZIPPED_SIZE MB) exceeds Lambda limit (250 MB)${NC}"
    exit 1
elif [ "$UNZIPPED_SIZE" -gt 200 ]; then
    echo -e "${YELLOW}NOTICE: Unzipped size ($UNZIPPED_SIZE MB) approaching Lambda limit (250 MB)${NC}"
fi

echo -e "${GREEN}Package ready for deployment!${NC}"
echo ""
echo "To deploy to Lambda:"
echo "  aws lambda update-function-code \\"
echo "    --function-name \$ENV-price-fetcher \\"
echo "    --zip-file fileb://$OUTPUT_FILE"
