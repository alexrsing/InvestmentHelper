#!/bin/bash
#
# Package Lambda deployment zip with slim dependencies
#
# Usage: ./deployment/package-lambda.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="/tmp/lambda-build-$$"
OUTPUT_FILE="$SCRIPT_DIR/lambda.zip"

echo "=== Hedgeye Risk Tracker Lambda Packager ==="
echo "Project root: $PROJECT_ROOT"
echo "Build dir: $BUILD_DIR"
echo "Output: $OUTPUT_FILE"
echo ""

# Clean up any previous build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Install slim dependencies
# Use --platform and --python-version to ensure we get Lambda-compatible binaries
# Lambda uses Amazon Linux 2023 with Python 3.13
echo "Installing dependencies from requirements-lambda.txt..."
pip install -r "$PROJECT_ROOT/requirements-lambda.txt" \
    -t "$BUILD_DIR" \
    --platform manylinux2014_x86_64 \
    --python-version 313 \
    --only-binary=:all: \
    --quiet 2>/dev/null || \
pip install -r "$PROJECT_ROOT/requirements-lambda.txt" -t "$BUILD_DIR" --quiet

# Copy source code
echo "Copying source code..."
cp -r "$PROJECT_ROOT/src/"* "$BUILD_DIR/"

# Remove unnecessary files to reduce size
echo "Cleaning up unnecessary files..."
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$BUILD_DIR" -type f -name "*.pyo" -delete 2>/dev/null || true

# Remove large unnecessary packages that might have been pulled in as dependencies
rm -rf "$BUILD_DIR/pandas" 2>/dev/null || true
rm -rf "$BUILD_DIR/numpy" 2>/dev/null || true
rm -rf "$BUILD_DIR/scipy" 2>/dev/null || true
rm -rf "$BUILD_DIR/matplotlib" 2>/dev/null || true

# Create zip
echo "Creating deployment package..."
rm -f "$OUTPUT_FILE"
cd "$BUILD_DIR"
zip -rq "$OUTPUT_FILE" .

# Clean up
rm -rf "$BUILD_DIR"

# Report size
SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
echo ""
echo "=== Package complete ==="
echo "Output: $OUTPUT_FILE"
echo "Size: $SIZE"
echo ""

# Warn if too large
SIZE_BYTES=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat -c%s "$OUTPUT_FILE" 2>/dev/null)
if [ "$SIZE_BYTES" -gt 52428800 ]; then
    echo "WARNING: Package exceeds 50MB. Consider further optimization."
elif [ "$SIZE_BYTES" -gt 70000000 ]; then
    echo "ERROR: Package exceeds 70MB limit for direct upload. Use S3 deployment."
    exit 1
fi
