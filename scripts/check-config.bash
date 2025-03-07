#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run the Python script using Poetry to ensure all dependencies are available
dotenvx run -- poetry run python "${SCRIPT_DIR}/check-config.py"
