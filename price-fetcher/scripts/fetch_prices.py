#!/usr/bin/env python3
"""
CLI entry point for fetching prices.

Usage:
    python scripts/fetch_prices.py [--force]

Options:
    --force, -f    Force refresh all symbols, ignoring staleness threshold
"""

import sys
from pathlib import Path

# Add fetchers directory to path
fetchers_dir = Path(__file__).parent.parent / "fetchers"
sys.path.insert(0, str(fetchers_dir))

from main import main

if __name__ == "__main__":
    main()
