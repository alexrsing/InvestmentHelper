#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Building Backend ==="
pip install -r "$ROOT_DIR/requirements.txt"

echo ""
echo "=== Building Frontend ==="
cd "$ROOT_DIR/frontend"
npm install
npm run build

echo ""
echo "=== Build complete ==="
