#!/usr/bin/env bash
# Runs the price-fetcher and hedgeye risk-range tracker in sequence.
# Usage: ./scripts/refresh-data.sh [--skip-validation]

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKIP_VALIDATION="${1:-}"

echo "=== Price Fetcher ==="
cd "$ROOT/price-fetcher"
uv run python fetchers/main.py --force

echo ""
echo "=== Hedgeye Risk Range Tracker ==="
cd "$ROOT/hedgeye-tracker"
if [ "$SKIP_VALIDATION" = "--skip-validation" ]; then
  uv run python src/main.py --skip-validation
else
  uv run python src/main.py
fi

echo ""
echo "=== Done ==="
