#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Building Backend ==="
cd "$ROOT_DIR"
uv sync

echo ""
echo "=== Building Frontend ==="
cd "$ROOT_DIR/frontend"
npm install
npm run build

echo ""
echo "=== Build complete ==="
